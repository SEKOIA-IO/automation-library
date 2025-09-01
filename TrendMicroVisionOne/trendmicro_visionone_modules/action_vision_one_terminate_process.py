from typing import Any

from .action_vision_one_base import TrendMicroVisionOneBaseAction


class TerminateProcessAction(TrendMicroVisionOneBaseAction):
    def run(self, arguments: Any) -> Any:
        agent_guid: str = arguments["agent_guid"]
        process_id: int = arguments["process_id"]

        file_sha1: str | None = arguments.get("file_sha1")
        file_name: str | None = arguments.get("file_name")
        description: str | None = arguments.get("description")

        if file_sha1 is None and file_name is None:
            self.log("You should provide either file's name or SHA-1 hash", level="critical")
            return

        base_url: str = self.module.configuration.base_url
        url = f"{base_url}/v3.0/response/endpoints/terminateProcess"

        payload: list[dict[str, Any]] = []
        item = {"agentGuid": agent_guid, "processId": process_id}
        if description:
            item["description"] = description

        if file_sha1:
            item["fileSha1"] = file_sha1

        if file_name:
            item["fileName"] = file_name

        payload.append(item)

        response = self.client.post(url, json=payload, timeout=60)
        return self.process_response(response)
