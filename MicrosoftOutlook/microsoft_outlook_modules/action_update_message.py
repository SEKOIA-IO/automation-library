from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .action_base import MicrosoftGraphActionBase


class UpdateMessageArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    user: str
    message_id: str
    content: str | None = None
    bcc: list[str] | None = None
    cc: list[str] | None = None
    sender: str | None = None
    from_: str | None = Field(default=None, alias="from")
    subject: str | None = None
    recipients: list[str] | None = None
    importance: Literal["Low", "Normal", "High"] | None = None


class UpdateMessageAction(MicrosoftGraphActionBase):
    @staticmethod
    def fill_non_empty(d: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in d.items() if v is not None}

    @staticmethod
    def generate_recipient(email: str) -> dict[str, Any]:
        return {"emailAddress": {"name": email, "address": email}}

    def run(self, arguments: Any) -> Any:
        validated_arguments = UpdateMessageArguments.model_validate(arguments)
        user_id_or_principal_name = validated_arguments.user
        message_id = validated_arguments.message_id

        content = validated_arguments.content
        bcc = validated_arguments.bcc
        cc = validated_arguments.cc
        sender = validated_arguments.sender
        mailbox_owner = validated_arguments.from_
        subject = validated_arguments.subject
        recipients = validated_arguments.recipients
        importance = validated_arguments.importance

        payload: dict[str, Any] = self.fill_non_empty(
            {
                "body": {"content": content, "contentType": "text"} if content else None,  # plain text
                "bccRecipients": [self.generate_recipient(item) for item in bcc] if bcc else None,
                "ccRecipients": [self.generate_recipient(item) for item in cc] if cc else None,
                "sender": self.generate_recipient(sender) if sender else None,
                "from": self.generate_recipient(mailbox_owner) if mailbox_owner else None,
                "subject": subject,
                "toRecipients": [self.generate_recipient(item) for item in recipients] if recipients else None,
                "importance": importance,
            }
        )

        response = self.client.patch(
            f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/messages/{message_id}",
            json=payload,
            timeout=60,
        )
        self.handle_response(response)

        return response.json()
