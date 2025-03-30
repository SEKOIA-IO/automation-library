from typing import Any

from .action_vision_one_base import TrendMicroVisionOneBaseAction


class AddAlertNoteAction(TrendMicroVisionOneBaseAction):
    def run(self, arguments: Any) -> Any:
        base_url: str = arguments["base_url"]
        api_key: str = arguments["api_key"]
        client = self.get_client(api_key)

        alert_id: list[str] = arguments["alert_id"]
        note: str = arguments["note"]

        url = f"{base_url}/v3.0/workbench/alerts/{alert_id}/notes"
        payload = {"content": note}

        response = client.post(url, json=payload, timeout=60)
        return self.process_response(response, headers_to_include=["Location"])
