from typing import Any, List, Optional

import requests
from pydantic import BaseModel, ConfigDict, Field

from .action_base import MicrosoftGraphActionBase
from .models import NonEmptyStr


class SendMessageArguments(BaseModel):
    user: NonEmptyStr = Field(..., description="User id or user principal name")
    save_to_sent_items: bool = Field(default=True, description="Whether to save the message to sent items")
    content: Optional[str] = None
    content_type: str = Field(default="text", description="Content type of the message body")
    bcc: Optional[List[str]] = None
    cc: Optional[List[str]] = None
    sender: Optional[str] = None
    from_: Optional[str] = Field(default=None, alias="from")
    subject: Optional[str] = None
    recipients: Optional[List[str]] = None
    importance: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class SendMessageAction(MicrosoftGraphActionBase):
    @staticmethod
    def generate_recipient(email: str) -> dict[str, Any]:
        return {"emailAddress": {"name": email, "address": email}}

    def run(self, arguments: SendMessageArguments) -> Any:
        user_id_or_principal_name = arguments.user
        save_to_sent_items = arguments.save_to_sent_items

        content = arguments.content
        content_type = arguments.content_type
        bcc = arguments.bcc
        cc = arguments.cc
        sender = arguments.sender
        mailbox_owner = arguments.from_
        subject = arguments.subject
        recipients = arguments.recipients
        importance = arguments.importance

        message: dict[str, Any] = {}
        if content:
            message["body"] = {"content": content, "contentType": content_type}
        if recipients:
            message["toRecipients"] = [self.generate_recipient(r) for r in recipients]
        if cc:
            message["ccRecipients"] = [self.generate_recipient(c) for c in cc]
        if bcc:
            message["bccRecipients"] = [self.generate_recipient(b) for b in bcc]
        if sender:
            message["sender"] = self.generate_recipient(sender)
        if mailbox_owner:
            message["from"] = self.generate_recipient(mailbox_owner)
        if subject:
            message["subject"] = subject
        if importance:
            message["importance"] = importance

        payload = {"message": message, "saveToSentItems": save_to_sent_items}

        response = self.client.post(
            f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/sendMail",
            json=payload,
            timeout=60,
        )
        self.handle_response(response)

        try:
            return response.json()

        except requests.exceptions.JSONDecodeError:
            return {}
