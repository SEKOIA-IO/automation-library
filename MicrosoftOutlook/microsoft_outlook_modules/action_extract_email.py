"""Extract embedded EML/MSG evidence from a message's attachments."""

from typing import Any

from pydantic import BaseModel, ConfigDict

from .action_base import MicrosoftGraphActionBase
from .attachments import collect_attachments
from .errors import AttachmentError, describe_error
from .graph import MailGraph


class ExtractEmailArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user: str
    message_id: str | dict[str, Any]


class ExtractEmailAction(MicrosoftGraphActionBase):
    def run(self, arguments: Any) -> dict[str, Any]:
        args = ExtractEmailArguments.model_validate(arguments)
        message_id = self._resolve_message_id(args.message_id)
        attachments, parsed, errors = collect_attachments(
            MailGraph(self.client),
            args.user,
            message_id,
            embedded_only=True,
        )
        for original in parsed:
            for attachment in original.get("nested_attachments", []):
                if attachment.get("processing_error"):
                    errors.append(
                        {
                            **describe_error(AttachmentError(attachment["processing_error"])),
                            "message_id": message_id,
                            "attachment_id": original["source_attachment_id"],
                            "attachment_name": attachment.get("name", ""),
                        }
                    )
        outcome = "partial" if errors and parsed else "failed" if errors else "succeeded"
        return self.report_item_errors(
            {
                "user": args.user,
                "message_id": message_id,
                "attachments": attachments,
                "parsed_emails": parsed,
                "errors": errors,
            },
            errors,
            outcome,
        )
