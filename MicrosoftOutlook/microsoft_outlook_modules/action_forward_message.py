from typing import Any

from pydantic import BaseModel, ConfigDict

from .action_base import MicrosoftGraphActionBase


class ForwardMessageArguments(BaseModel):
    """Represent validated inputs for the forward message action."""

    model_config = ConfigDict(extra="forbid")

    user: str
    message_id: str | dict[str, Any]
    recipients: list[str]
    comment: str = ""


class ForwardMessageAction(MicrosoftGraphActionBase):
    def run(self, arguments: Any) -> Any:
        """Execute the forward message action and return action metadata."""

        validated_arguments = ForwardMessageArguments.model_validate(arguments)
        user_id_or_principal_name = validated_arguments.user
        message_id = self._resolve_message_id(validated_arguments.message_id)
        recipients = validated_arguments.recipients
        comment = validated_arguments.comment

        self.log(
            message=(
                "Start forward message action "
                f"user={user_id_or_principal_name!r} "
                f"message_id={message_id!r} "
                f"recipient_count={len(recipients)!r}"
            ),
            level="debug",
        )

        payload: dict[str, Any] = {
            "comment": comment,
            "toRecipients": [self._generate_recipient(recipient) for recipient in recipients],
        }

        response = self.client.post(
            f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/messages/{message_id}/forward",
            json=payload,
            timeout=60,
        )
        self.handle_response(response)

        self.log(
            message=(
                "Completed forward message action "
                f"user={user_id_or_principal_name!r} "
                f"message_id={message_id!r} "
                f"recipient_count={len(recipients)!r}"
            ),
            level="debug",
        )

        return {
            "status": "forwarded",
            "action": "forward_message",
            "comment": comment,
            "target_message_id": message_id,
            "user": user_id_or_principal_name,
            "recipients": recipients,
        }
