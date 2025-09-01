from typing import Any

from .action_vision_one_base import TrendMicroVisionOneBaseAction


class CollectFileAction(TrendMicroVisionOneBaseAction):
    def run(self, arguments: Any) -> Any:
        agent_guids: list[str] = arguments["agent_guids"]
        description: str | None = arguments.get("description")
        file_path: str = arguments["file_path"]

        base_url: str = self.module.configuration.base_url
        url = f"{base_url}/v3.0/response/endpoints/collectFile"

        payload: list[dict[str, Any]] = []
        for agent_guid in agent_guids:
            item = {"agentGuid": agent_guid, "filePath": file_path}

            if description:
                item["description"] = description

            payload.append(item)

        response = self.client.post(url, json=payload, timeout=60)
        return self.process_response(response)
