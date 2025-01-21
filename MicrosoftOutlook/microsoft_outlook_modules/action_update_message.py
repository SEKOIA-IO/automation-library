from typing import Any

from .action_base import MicrosoftGraphActionBase


class UpdateMessageAction(MicrosoftGraphActionBase):
    @staticmethod
    def fill_non_empty(d: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in d.items() if v is not None}

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
                "body": content,
                "bccRecipients": bcc,
                "ccRecipients": cc,
                "sender": sender,
                "from": mailbox_owner,
                "subject": subject,
                "toRecipients": recipients,
                "importance": importance,
            }
        )

        response = self.client.patch(
            f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/messages/{message_id}",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()

        return response.json()
