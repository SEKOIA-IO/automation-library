from typing import Any

from . import TrendMicroVisionOneModule
from .action_vision_one_base import TrendMicroVisionOneBaseAction


class TerminateProcessAction(TrendMicroVisionOneBaseAction):
    def run(self, arguments: Any) -> Any:
        agent_guids: list[str] = arguments["agent_guids"]
        file_sha1: str = arguments["file_sha1"]
        file_name: str | None = arguments.get("file_name")
        description: str | None = arguments.get("description")

        base_url: str = self.module.configuration.base_url
        url = f"{base_url}/v3.0/response/endpoints/terminateProcess"

        payload: list[dict[str, Any]] = []
        for agent_guid in agent_guids:
            item = {"agentGuid": agent_guid, "fileSha1": file_sha1}
            if description:
                item["description"] = description

            if file_name:
                item["fileName"] = file_name

            payload.append(item)

        response = self.client.post(url, json=payload, timeout=60)
        return self.process_response(response)
