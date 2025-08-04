from typing import Any

from .action_base import MicrosoftGraphActionBase


class UpdateMessageAction(MicrosoftGraphActionBase):
    @staticmethod
    def fill_non_empty(d: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in d.items() if v is not None}

    @staticmethod
    def generate_recipient(email: str) -> dict[str, Any]:
        return {"emailAddress": {"name": email, "address": email}}

    def run(self, arguments: Any) -> Any:
        user_id_or_principal_name = arguments["user"]
        message_id = arguments["message_id"]

        content = arguments.get("content")
        bcc: list[str] | None = arguments.get("bcc")
        cc: list[str] | None = arguments.get("cc")
        sender = arguments.get("sender")
        mailbox_owner = arguments.get("from")
        subject = arguments.get("subject")
        recipients: list[str] | None = arguments.get("recipients")
        importance = arguments.get("importance")

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
