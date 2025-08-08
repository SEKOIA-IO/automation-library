from typing import Any

from .action_vision_one_base import TrendMicroVisionOneBaseAction


class UpdateAlertAction(TrendMicroVisionOneBaseAction):
    def run(self, arguments: Any) -> Any:
        alert_id: list[str] = arguments["alert_id"]
        status: str = arguments.get("status")
        investigation_result: str = arguments.get("investigation_result")

        base_url: str = self.module.configuration.base_url
        url = f"{base_url}/v3.0/workbench/alerts/{alert_id}"
        payload = {}
        if status:
            payload["status"] = status

        if investigation_result:
            payload["investigationResult"] = investigation_result

        response = self.client.patch(url, json=payload, timeout=60)
        return self.process_response(response)
