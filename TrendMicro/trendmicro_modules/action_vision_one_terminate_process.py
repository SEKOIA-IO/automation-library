from typing import Any

from .action_vision_one_base import TrendMicroVisionOneBaseAction


class TerminateProcessAction(TrendMicroVisionOneBaseAction):
    def run(self, arguments: Any) -> Any:
        base_url: str = arguments["base_url"]
        api_key: str = arguments["api_key"]
        client = self.get_client(api_key)

        agent_guids: list[str] = arguments["agent_guids"]
        file_sha1: str = arguments["file_sha1"]
        file_name: str | None = arguments.get("file_name")
        description: str | None = arguments.get("description")

        url = f"{base_url}/v3.0/response/endpoints/terminateProcess"

        payload = []
        for agent_guid in agent_guids:
            item = {"agentGuid": agent_guid, "fileSha1": file_sha1}
            if description:
                item["description"] = description

            if file_name:
                item["fileName"] = file_name

            payload.append(item)

        response = client.post(url, json=payload, timeout=60)
        return self.process_response(response)
