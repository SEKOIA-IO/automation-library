"""List a bounded page from a folder, with explicit continuation information."""

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

from .action_base import MicrosoftGraphActionBase
from .graph import MailGraph, odata_escape
from .message_ids import graph_message_id


class ListMessagesArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user: str
    folder: str = "inbox"
    subject_filter: str | None = None
    sender_filter: str | None = None
    email_message_id: str | None = None
    timeframe_minutes: int | None = Field(default=None, ge=1)
    max_messages_to_return: int = Field(default=25, ge=1, le=100)
    only_unread: bool = False


class ListMessagesAction(MicrosoftGraphActionBase):
    def run(self, arguments: Any) -> dict[str, Any]:
        args = ListMessagesArguments.model_validate(arguments)
        internet_message_id = None
        if args.email_message_id:
            internet_message_id = graph_message_id(args.email_message_id)
        graph = MailGraph(self.client)
        folder = graph.folder(args.user, args.folder)
        cutoff = "1900-01-01T00:00:00Z"
        if args.timeframe_minutes:
            cutoff = (datetime.now(UTC) - timedelta(minutes=args.timeframe_minutes)).isoformat()
        filters = [f"receivedDateTime ge {cutoff}"]
        if args.subject_filter:
            filters.append(f"contains(subject, '{odata_escape(args.subject_filter)}')")
        if args.sender_filter:
            filters.append(f"from/emailAddress/address eq '{odata_escape(args.sender_filter)}'")
        if internet_message_id:
            filters.append(f"internetMessageId eq '{odata_escape(internet_message_id)}'")
        if args.only_unread:
            filters.append("isRead eq false")
        payload = graph.page(
            f"{graph.user_path(args.user)}/mailFolders/{quote(folder['id'], safe='')}/messages",
            {
                "$filter": " and ".join(filters),
                "$orderby": "receivedDateTime desc",
                "$top": args.max_messages_to_return,
                "$select": "id,internetMessageId,parentFolderId,subject,from,toRecipients,receivedDateTime,isRead",
            },
        )
        messages = self._snake_case_keys(payload.get("value", []))
        for message in messages:
            message["message_id"] = message.pop("id")
        return {
            "user": args.user,
            "folder_id": folder["id"],
            "folder_name": folder["displayName"],
            "messages": messages,
            "message_ids": [m["message_id"] for m in messages],
            "returned_count": len(messages),
            "has_more": bool(payload.get("@odata.nextLink")),
        }
