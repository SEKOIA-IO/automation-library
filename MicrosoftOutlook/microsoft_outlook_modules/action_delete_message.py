from typing import Any

from pydantic import BaseModel, ConfigDict

from .action_base import MicrosoftGraphActionBase


class DeleteMessageArguments(BaseModel):
    """Represent validated inputs for the delete message action."""

    model_config = ConfigDict(extra="forbid")

    user: str
    message_id: str | dict[str, Any]


class DeleteMessageAction(MicrosoftGraphActionBase):
    def run(self, arguments: Any) -> Any:
        """Execute the delete message action and return action metadata."""

        validated_arguments = DeleteMessageArguments.model_validate(arguments)
        user_id_or_principal_name = validated_arguments.user
        message_id = self._resolve_message_id(validated_arguments.message_id)

        self.log(
            message=(f"Start delete message action user={user_id_or_principal_name!r} message_id={message_id!r}"),
            level="debug",
        )

        response = self.client.delete(
            f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/messages/{message_id}",
            timeout=60,
        )
        self.handle_response(response)

        self.log(
            message=(f"Completed delete message action user={user_id_or_principal_name!r} message_id={message_id!r}"),
            level="debug",
        )

        return {
            "status": "deleted",
            "action": "delete_a_message",
            "target_message_id": message_id,
            "user": user_id_or_principal_name,
        }
