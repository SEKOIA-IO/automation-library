from typing import Any

from pydantic import BaseModel, Field

from actions.base import MoknBaseAction


class RequestCredentialCheckArguments(BaseModel):
    attempt_id: int = Field(..., description="Identifier of the MokN login attempt")


class RequestCredentialCheckAction(MoknBaseAction):
    name = "Request MokN credential check"
    description = "Request a credential check for a specific MokN login attempt"

    def run(self, arguments: RequestCredentialCheckArguments) -> dict[str, Any]:
        response = self.service.request_credential_check(arguments.attempt_id)
        return self.build_result(response, "Credential check requested successfully")
