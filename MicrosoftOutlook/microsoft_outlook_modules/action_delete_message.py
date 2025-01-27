from typing import Any

from .action_base import MicrosoftGraphActionBase


class DeleteMessageAction(MicrosoftGraphActionBase):
    def run(self, arguments: Any) -> Any:
        user_id_or_principal_name = arguments["user"]
        message_id = arguments["message_id"]

        response = self.client.delete(
            f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/messages/{message_id}",
            timeout=60,
        )
        self.handle_response(response)
