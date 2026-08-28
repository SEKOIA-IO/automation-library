from typing import Any

from pydantic import BaseModel, ConfigDict

from .action_base import MicrosoftGraphActionBase


class GetMessageArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: str
    message_id: str


class GetMessageAction(MicrosoftGraphActionBase):
    def run(self, arguments: Any) -> Any:
        validated_arguments = GetMessageArguments.model_validate(arguments)
        user_id_or_principal_name = validated_arguments.user
        message_id = validated_arguments.message_id

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
            normalized_result["message_id"] = resolved_message_id
            return normalized_result
        return result
