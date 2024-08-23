from typing import Any, Literal

from pydantic import BaseModel

from withsecure.models import ResponseActionResponse
from withsecure.response_action import ResponseAction


class ActionArguments(BaseModel):
    target: str
    organization_id: str

    match: Literal["processId", "processName", "processNameRegex", "processPath", "processPathRegex"]
    process_match_values: list[str]  # min items: 1, max items: 6

    process_memory_dump: bool = False
    memory_dump_flag: Literal["full", "pmem"]  # allowed values: full, pmem


class KillProcess(ResponseAction):
    results_model = ResponseActionResponse

    def run(self, arguments: ActionArguments) -> Any:
        parameters = {
            "match": arguments.match,
            "processMatchValues": arguments.process_match_values,
            "processMemoryDump": arguments.process_memory_dump,
            "memoryDumpFlag": arguments.memory_dump_flag,
        }

        response = self._execute_operation_on_device(
            action_type="killProcess",
            organization_id=arguments.organization_id,
            target=arguments.target,
            parameters=parameters,
        )

        return ResponseActionResponse(id=response.get("id"))
