from typing import Any

from pydantic import BaseModel, ConfigDict

from .action_base import MicrosoftGraphActionBase


class ForwardMessageArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: str
    message_id: str
    recipients: list[str]
    comment: str = ""


class ForwardMessageAction(MicrosoftGraphActionBase):
    def run(self, arguments: Any) -> Any:
        validated_arguments = ForwardMessageArguments.model_validate(arguments)
        user_id_or_principal_name = validated_arguments.user
        message_id = validated_arguments.message_id
        recipients = validated_arguments.recipients
        comment = validated_arguments.comment

        payload: dict[str, Any] = {
            "comment": comment,
            "toRecipients": [{"emailAddress": {"name": recipient, "address": recipient}} for recipient in recipients],
        }

        response = self.client.post(
            f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/messages/{message_id}/forward",
            json=payload,
            timeout=60,
        )
        self.handle_response(response)

        return {
            "status": "forwarded",
            "action": "forward_message",
            "target_message_id": message_id,
        }
