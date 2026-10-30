from typing import Any

from pydantic import BaseModel, ConfigDict

from .action_base import MicrosoftGraphActionBase


class GetMessageArguments(BaseModel):
    """Represent validated inputs for the get message action."""

    model_config = ConfigDict(extra="forbid")

    user: str
    message_id: str | dict[str, Any]


class GetMessageAction(MicrosoftGraphActionBase):
    def run(self, arguments: Any) -> Any:
        """Execute the get message action and return normalized results."""

        validated_arguments = GetMessageArguments.model_validate(arguments)
        user_id_or_principal_name = validated_arguments.user
        message_id = self._resolve_message_id(validated_arguments.message_id)

        self.log(
            message=(f"Start get message action user={user_id_or_principal_name!r} message_id={message_id!r}"),
            level="debug",
        )

        response = self.client.get(
            f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/messages/{message_id}",
            timeout=60,
        )
        self.handle_response(response)

        result = response.json()
        if isinstance(result, dict):
            resolved_message_id = result.get("id") if isinstance(result.get("id"), str) else message_id
            normalized_result = self._snake_case_keys(result)
            normalized_result.pop("id", None)
            normalized_result["user"] = user_id_or_principal_name
            normalized_result["message_id"] = resolved_message_id
            self.log(
                message=(
                    "Completed get message action "
                    f"user={user_id_or_principal_name!r} "
                    f"message_id={resolved_message_id!r}"
                ),
                level="debug",
            )
            return normalized_result
        return result
