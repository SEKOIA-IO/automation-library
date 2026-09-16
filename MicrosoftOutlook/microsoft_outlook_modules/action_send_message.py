from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .action_base import MicrosoftGraphActionBase


class SendMessageArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    user: str
    content: str
    content_type: Literal["text", "html"] = "text"
    bcc: list[str] | None = None
    cc: list[str] | None = None
    sender: str
    from_: str = Field(alias="from")
    subject: str
    recipients: list[str]
    importance: Literal["Low", "Normal", "High"] | None = None
    save_to_sent_items: bool = True


class SendMessageAction(MicrosoftGraphActionBase):
    @staticmethod
    def generate_recipient(email: str) -> dict[str, Any]:
        return {"emailAddress": {"name": email, "address": email}}

    def run(self, arguments: Any) -> Any:
        validated_arguments = SendMessageArguments.model_validate(arguments)
        user_id_or_principal_name = validated_arguments.user
        save_to_sent_items = validated_arguments.save_to_sent_items

        content = validated_arguments.content
        content_type = validated_arguments.content_type
        bcc = validated_arguments.bcc
        cc = validated_arguments.cc
        sender = validated_arguments.sender
        mailbox_owner = validated_arguments.from_
        subject = validated_arguments.subject
        recipients = validated_arguments.recipients
        importance = validated_arguments.importance

        message: dict[str, Any] = {
            "body": {"content": content, "contentType": content_type},
            "toRecipients": [self.generate_recipient(r) for r in recipients],
            "sender": self.generate_recipient(sender),
            "from": self.generate_recipient(mailbox_owner),
            "subject": subject,
        }
        if cc:
            message["ccRecipients"] = [self.generate_recipient(c) for c in cc]
        if bcc:
            message["bccRecipients"] = [self.generate_recipient(b) for b in bcc]
        if importance:
            message["importance"] = importance

        payload: dict[str, Any] = {"message": message, "saveToSentItems": save_to_sent_items}

        response = self.client.post(
            f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/sendMail",
            json=payload,
            timeout=60,
        )
        self.handle_response(response)

        response_data: dict[str, Any] = {}
        try:
            parsed_body = response.json()
            if isinstance(parsed_body, dict):
                response_data = parsed_body

        except ValueError:
            response_data = {}

        target_message_id = response_data.get("id") if isinstance(response_data.get("id"), str) else None
        return {
            **response_data,
            "status": "sent",
            "action": "send_message",
            "target_message_id": target_message_id,
        }
