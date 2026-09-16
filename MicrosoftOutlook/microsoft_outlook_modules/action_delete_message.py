from typing import Any

from pydantic import BaseModel, ConfigDict

from .action_base import MicrosoftGraphActionBase


class DeleteMessageArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: str
    message_id: str


class DeleteMessageAction(MicrosoftGraphActionBase):
    def run(self, arguments: Any) -> Any:
        validated_arguments = DeleteMessageArguments.model_validate(arguments)
        user_id_or_principal_name = validated_arguments.user
        message_id = validated_arguments.message_id

        response = self.client.delete(
            f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/messages/{message_id}",
            timeout=60,
        )
        self.handle_response(response)

        return {
            "status": "deleted",
            "action": "delete_a_message",
            "target_message_id": message_id,
        }
