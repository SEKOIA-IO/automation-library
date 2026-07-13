from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .action_base import MicrosoftGraphActionBase
from .models import NonEmptyStr


class UpdateMessageArguments(BaseModel):
    user: NonEmptyStr = Field(..., description="User id or user principal name")
    message_id: NonEmptyStr = Field(..., description="Message id")
    content: Optional[str] = None
    bcc: Optional[List[str]] = None
    cc: Optional[List[str]] = None
    sender: Optional[str] = None
    from_: Optional[str] = Field(default=None, alias="from")
    subject: Optional[str] = None
    recipients: Optional[List[str]] = None
    importance: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class UpdateMessageAction(MicrosoftGraphActionBase):
    @staticmethod
    def fill_non_empty(d: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in d.items() if v is not None}

    @staticmethod
    def generate_recipient(email: str) -> dict[str, Any]:
        return {"emailAddress": {"name": email, "address": email}}

    def run(self, arguments: UpdateMessageArguments) -> Any:
        user_id_or_principal_name = arguments.user
        message_id = arguments.message_id

        content = arguments.content
        bcc = arguments.bcc
        cc = arguments.cc
        sender = arguments.sender
        mailbox_owner = arguments.from_
        subject = arguments.subject
        recipients = arguments.recipients
        importance = arguments.importance

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
