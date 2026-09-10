from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .action_vision_one_base import TrendMicroVisionOneBaseAction


class TerminateProcessArguments(BaseModel):
    agent_guid: UUID = Field(..., description="The identifiers of the endpoints to isolate")
    process_id: int = Field(..., gt=0, description="Process ID to terminate")
    file_sha1: Optional[str] = None
    file_name: Optional[str] = None
    description: Optional[str] = None


class TerminateProcessAction(TrendMicroVisionOneBaseAction):
    def run(self, arguments: TerminateProcessArguments) -> Any:
        agent_guid = arguments.agent_guid
        process_id = arguments.process_id
        file_sha1 = arguments.file_sha1
        file_name = arguments.file_name
        description = arguments.description

        if file_sha1 is None and file_name is None:
            self.log("You should provide either file's name or SHA-1 hash", level="critical")
            return

        base_url: str = self.module.configuration.base_url
        url = f"{base_url}/v3.0/response/endpoints/terminateProcess"

        payload: list[dict[str, Any]] = []
        item = {"agentGuid": str(agent_guid), "processId": process_id}
        if description:
            item["description"] = description

        if file_sha1:
            item["fileSha1"] = file_sha1

        if file_name:
            item["fileName"] = file_name

        payload.append(item)

        response = self.client.post(url, json=payload, timeout=60)
        return self.process_response(response)
