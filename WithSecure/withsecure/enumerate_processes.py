from typing import Any

from pydantic import BaseModel

from withsecure.models import ResponseActionResponse
from withsecure.response_action import ResponseAction


class ActionArguments(BaseModel):
    target: str
    organization_id: str

    max_file_hash: int | None = None


class EnumerateProcesses(ResponseAction):
    results_model = ResponseActionResponse

    def run(self, arguments: ActionArguments) -> Any:

        response = self._execute_operation_on_device(
            action_type="enumerateProcesses",
            organization_id=arguments.organization_id,
            target=arguments.target,
        )

        return ResponseActionResponse(id=response.get("id"))
