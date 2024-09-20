from typing import Any

from pydantic import BaseModel

from withsecure.models import ResponseActionResponse
from withsecure.response_action import ResponseAction


class ActionArguments(BaseModel):
    target: str
    organization_id: str

    thread_id: int


class KillThread(ResponseAction):
    results_model = ResponseActionResponse

    def run(self, arguments: ActionArguments) -> Any:
        parameters = {"threadId": arguments.thread_id}

        response = self._execute_operation_on_device(
            action_type="killThread",
            organization_id=arguments.organization_id,
            target=arguments.target,
            parameters=parameters,
        )

        return ResponseActionResponse(id=response.get("id"))
