from typing import Any

from pydantic import BaseModel

from withsecure.models import ResponseActionResponse
from withsecure.response_action import ResponseAction


class ActionArguments(BaseModel):
    target: str
    organization_id: str

    match: str  # allowed values: processId, processName, processNameRegex, processPath, processPathRegex
    process_match_values: list[str]  # min items: 1, max items: 6

    process_memory_dump: bool
    memory_dump_flag: str  # allowed values: full, pmem


class KillProcess(ResponseAction):
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
