from typing import Any

from .action_vision_one_base import TrendMicroVisionOneBaseAction


class ScanMachineAction(TrendMicroVisionOneBaseAction):
    def run(self, arguments: Any) -> Any:
        agent_guids: list[str] = arguments["agent_guids"]
        description: str | None = arguments.get("description")

        base_url: str = self.module.configuration.base_url
        url = f"{base_url}/v3.0/response/endpoints/startMalwareScan"

        payload: dict[str, Any] = {"endpoints": []}
        for agent_guid in agent_guids:
            item = {"agentGuid": agent_guid}

            if description:
                item["description"] = description

            payload["endpoints"].append(item)

        response = self.client.post(url, json=payload, timeout=60)
        return self.process_response(response, headers_to_include=["Operation-Location"])
