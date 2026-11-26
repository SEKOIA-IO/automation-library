"""Export the MIME bytes provided by Graph to playbook shared storage."""

import hashlib
from typing import Any
from uuid import uuid4

from pydantic import Field
from s3path import S3Path

from .action_base import MicrosoftGraphActionBase
from .action_extract_email import ExtractEmailArguments
from .errors import AttachmentError
from .graph import MailGraph


class ExportMessageArguments(ExtractEmailArguments):
    max_size_mb: int = Field(default=25, ge=1, le=100)


class ExportMessageAction(MicrosoftGraphActionBase):
    def run(self, arguments: Any) -> dict[str, Any]:
        args = ExportMessageArguments.model_validate(arguments)
        message_id = self._resolve_message_id(args.message_id)
        graph = MailGraph(self.client)
        filename = f"outlook-{uuid4()}.eml"
        destination = self.data_path / filename
        cloud = isinstance(self.data_path, S3Path)
        size = 0
        digest = hashlib.sha256()
        opened = False
        try:
            with graph.request("GET", f"{graph.message_url(args.user, message_id)}/$value", stream=True) as response:
                # Check both advertised and streamed size; no API-provided filename is used as a path.
                length = response.headers.get("Content-Length", "")
                if length.isdigit() and int(length) > args.max_size_mb * 1024 * 1024:
                    raise AttachmentError("Message exceeds max_size_mb; no EML file was exported.")
                with destination.open("wb" if cloud else "xb") as output:
                    opened = True
                    for chunk in response.iter_content(chunk_size=65536):
                        size += len(chunk)
                        if size > args.max_size_mb * 1024 * 1024:
                            raise AttachmentError("Message exceeds max_size_mb; no EML file was exported.")
                        output.write(chunk)
                        digest.update(chunk)
                    if size == 0:
                        raise AttachmentError("Graph returned an empty message; no EML file was exported.")
        except Exception:
            if opened:
                try:
                    destination.unlink(missing_ok=True)
                except Exception:
                    raise AttachmentError(
                        "EML export failed and its incomplete file could not be removed. Check shared storage."
                    ) from None
            raise
        return {
            "user": args.user,
            "message_id": message_id,
            "file_path": filename,
            "file_name": filename,
            "content_type": "message/rfc822",
            "size": size,
            "sha256": digest.hexdigest(),
        }
