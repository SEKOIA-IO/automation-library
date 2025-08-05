from typing import Any

from .action_vision_one_base import TrendMicroVisionOneBaseAction


class AddAlertNoteAction(TrendMicroVisionOneBaseAction):
    def run(self, arguments: Any) -> Any:
        alert_id: list[str] = arguments["alert_id"]
        note: str = arguments["note"]

        base_url: str = self.module.configuration.base_url
        url = f"{base_url}/v3.0/workbench/alerts/{alert_id}/notes"
        payload = {"content": note}

        response = self.client.post(url, json=payload, timeout=60)
        return self.process_response(response, headers_to_include=["Location"])
