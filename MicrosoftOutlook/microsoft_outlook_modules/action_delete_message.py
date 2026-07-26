from typing import Any

from pydantic import BaseModel, Field

from .action_base import MicrosoftGraphActionBase
from .models import NonEmptyStr


class DeleteMessageArguments(BaseModel):
    user: NonEmptyStr = Field(..., description="User id or user principal name")
    message_id: NonEmptyStr = Field(..., description="Message id")


class DeleteMessageAction(MicrosoftGraphActionBase):
    def run(self, arguments: DeleteMessageArguments) -> Any:
        user_id_or_principal_name = arguments.user
        message_id = arguments.message_id

        response = self.client.delete(
            f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/messages/{message_id}",
            timeout=60,
        )
        self.handle_response(response)
