from typing import Any

from .action_base import MicrosoftGraphActionBase


class ForwardMessageAction(MicrosoftGraphActionBase):
    def run(self, arguments: Any) -> Any:
        user_id_or_principal_name = arguments["user"]
        message_id = arguments["message_id"]
        recipients: list[str] = arguments["recipients"]

        comment = arguments.get("comment", "")

        payload = {
            "comment": comment,
            "toRecipients": [{"emailAddress": {"name": recipient, "address": recipient}} for recipient in recipients],
        }

        response = self.client.post(
            f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/messages/{message_id}/forward",
            json=payload,
            timeout=60,
        )
        self.handle_response(response)
