from typing import Any
from urllib.parse import urljoin

from .action_base import MicrosoftDefenderBaseAction


class UnIsolateMachineAction(MicrosoftDefenderBaseAction):
    def run(self, arguments: Any) -> Any:
        machine_id = arguments["machine_id"]
        comment = arguments["comment"]

        data = {"Comment": comment}

        url = urljoin(self.client.base_url, f"api/machines/{machine_id}/unisolate")
        response = self.client.post(url, json=data)

        self.process_response(response)
        return response.json()
