from typing import Any

from .action_vision_one_base import TrendMicroVisionOneBaseAction


class TerminateProcessAction(TrendMicroVisionOneBaseAction):
    def run(self, arguments: Any) -> Any:
        agent_guids_process_ids: list[dict] = arguments["agent_guids_process_ids"]

        file_sha1: str | None = arguments.get("file_sha1")
        file_name: str | None = arguments.get("file_name")
        description: str | None = arguments.get("description")

        base_url: str = self.module.configuration.base_url
        url = f"{base_url}/v3.0/response/endpoints/terminateProcess"

        payload: list[dict[str, Any]] = []
        for group in agent_guids_process_ids:
            item = {"agentGuid": group["agent_guid"], "processId": group["process_id"]}
            if description:
                item["description"] = description

            if file_sha1:
                item["fileSha1"] = file_sha1

            if file_name:
                item["fileName"] = file_name

            payload.append(item)

        response = self.client.post(url, json=payload, timeout=60)
        return self.process_response(response)
