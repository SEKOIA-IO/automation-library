from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .action_vision_one_base import TrendMicroVisionOneBaseAction


class IsolateMachineArguments(BaseModel):
    agent_guids: list[UUID] = Field(..., min_length=1, description="Agent GUIDs")
    description: Optional[str] = None


class IsolateMachineAction(TrendMicroVisionOneBaseAction):
    def run(self, arguments: IsolateMachineArguments) -> Any:
        agent_guids = arguments.agent_guids
        description = arguments.description

        base_url: str = self.module.configuration.base_url
        url = f"{base_url}/v3.0/response/endpoints/isolate"

        payload: list[dict[str, Any]] = []
        for agent_guid in agent_guids:
            item = {"agentGuid": str(agent_guid)}

            if description:
                item["description"] = description

            payload.append(item)

        response = self.client.post(url, json=payload, timeout=60)
        return self.process_response(response)
