"""Download bounded attachments and expose exact-byte evidence hashes."""

from typing import Any

from .action_base import MicrosoftGraphActionBase
from .action_extract_email import ExtractEmailArguments
from .attachments import collect_attachments
from .graph import MailGraph


class DownloadAttachmentsAction(MicrosoftGraphActionBase):
    def run(self, arguments: Any) -> dict[str, Any]:
        args = ExtractEmailArguments.model_validate(arguments)
        message_id = self._resolve_message_id(args.message_id)
        attachments, _, errors = collect_attachments(
            MailGraph(self.client),
            args.user,
            message_id,
            include_content=True,
            parse_messages=False,
        )
        downloaded = any("base64_content" in item for item in attachments)
        outcome = "partial" if errors and downloaded else "failed" if errors else "succeeded"
        return self.report_item_errors(
            {"user": args.user, "message_id": message_id, "attachments": attachments, "errors": errors},
            errors,
            outcome,
        )
