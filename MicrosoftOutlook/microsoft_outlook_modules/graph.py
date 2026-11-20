"""Bounded Graph mail operations shared by Outlook actions and connector."""

from typing import Any
from urllib.parse import quote, urlsplit

from requests import Session

from .errors import AttachmentError, IncompleteResultsError

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
MAX_ATTACHMENT_SIZE = 4 * 1024 * 1024
REQUEST_TIMEOUT = (10, 30)


def odata_escape(value: str) -> str:
    return value.replace("'", "''")


class MailGraph:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def user_path(user: str) -> str:
        return f"{GRAPH_ROOT}/users/{quote(user, safe='')}"

    @staticmethod
    def check_url(url: str) -> None:
        parsed = urlsplit(url)
        if (parsed.scheme, parsed.netloc) != ("https", "graph.microsoft.com"):
            raise ValueError("Unexpected Graph pagination URL")
        if not parsed.path.startswith("/v1.0/") or parsed.fragment:
            raise ValueError("Unexpected Graph pagination path")

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        self.check_url(url)
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        kwargs.setdefault("allow_redirects", False)
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        if 300 <= response.status_code < 400:
            response.close()
            raise ValueError("Unexpected redirect from Microsoft Graph")
        return response

    def json(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        response = self.request(method, url, **kwargs)
        return response.json() if response.content else {}

    def page(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.json("GET", url, params=params)

    def collection(self, url: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for _ in range(50):
            payload = self.page(url, params)
            records.extend(payload.get("value", []))
            url = payload.get("@odata.nextLink", "")
            if not url:
                return records
            params = None
        raise IncompleteResultsError("Graph pagination limit reached; results are incomplete")

    def folder(self, user: str, folder: str) -> dict[str, Any]:
        # IDs and Graph well-known folder names are explicit, not inferred from length.
        # Display names can be resolved by list_folders; ambiguous names never select the first match.
        return self.json(
            "GET",
            f"{self.user_path(user)}/mailFolders/{quote(folder, safe='')}",
            params={"$select": "id,displayName"},
        )

    def message_url(self, user: str, message_id: str) -> str:
        return f"{self.user_path(user)}/messages/{quote(message_id, safe='')}"

    def attachments(self, user: str, message_id: str) -> list[dict[str, Any]]:
        return self.collection(
            f"{self.message_url(user, message_id)}/attachments",
            params={"$select": "id,name,contentType,size"},
        )

    def attachment_bytes(self, user: str, message_id: str, attachment: dict[str, Any]) -> bytes:
        import base64

        if (attachment.get("size") or 0) > MAX_ATTACHMENT_SIZE:
            raise AttachmentError("Attachment exceeds the 4 MiB processing limit")
        content = attachment.get("contentBytes")
        if content is not None:
            if len(content) > ((MAX_ATTACHMENT_SIZE + 2) // 3) * 4:
                raise AttachmentError("Attachment exceeds the 4 MiB processing limit")
            raw = base64.b64decode(content, validate=True)
        else:
            url = f"{self.message_url(user, message_id)}/attachments/{quote(attachment['id'], safe='')}/$value"
            # A streamed download enforces the limit even when Graph omits/understates size.
            with self.request("GET", url, stream=True) as response:
                chunks = bytearray()
                for chunk in response.iter_content(chunk_size=65536):
                    chunks.extend(chunk)
                    if len(chunks) > MAX_ATTACHMENT_SIZE:
                        raise AttachmentError("Attachment exceeds the 4 MiB processing limit")
                raw = bytes(chunks)
        if len(raw) > MAX_ATTACHMENT_SIZE:
            raise AttachmentError("Attachment exceeds the 4 MiB processing limit")
        return raw
