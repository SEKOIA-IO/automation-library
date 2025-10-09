from typing import Any

import requests

from .action_base import MicrosoftGraphActionBase


class SendMessageAction(MicrosoftGraphActionBase):
    @staticmethod
    def generate_recipient(email: str) -> dict[str, Any]:
        return {"emailAddress": {"name": email, "address": email}}

    def run(self, arguments: Any) -> Any:
        user_id_or_principal_name = arguments["user"]
        save_to_sent_items = arguments.get("save_to_sent_items", True)

        content = arguments.get("content")
        content_type = arguments.get("content_type", "text")
        bcc: list[str] | None = arguments.get("bcc")
        cc: list[str] | None = arguments.get("cc")
        sender = arguments.get("sender")
        mailbox_owner = arguments.get("from")
        subject = arguments.get("subject")
        recipients: list[str] | None = arguments.get("recipients")
        importance = arguments.get("importance")

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
