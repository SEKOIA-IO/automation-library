from typing import Any, List

from pydantic import BaseModel, Field

from .action_base import MicrosoftGraphActionBase
from .models import NonEmptyStr


class ForwardMessageArguments(BaseModel):
    user: NonEmptyStr = Field(..., description="User id or user principal name")
    message_id: NonEmptyStr = Field(..., description="Message id")
    recipients: List[str] = Field(..., description="Recipients to forward the message to")
    comment: str = Field(default="", description="Comment to add to the forwarded message")


class ForwardMessageAction(MicrosoftGraphActionBase):
    def run(self, arguments: ForwardMessageArguments) -> Any:
        user_id_or_principal_name = arguments.user
        message_id = arguments.message_id
        recipients = arguments.recipients

        comment = arguments.comment

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
