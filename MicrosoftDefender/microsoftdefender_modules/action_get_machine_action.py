from typing import Any
from urllib.parse import urljoin

from .action_base import MicrosoftDefenderBaseAction


class GetMachineAction(MicrosoftDefenderBaseAction):
    def run(self, arguments: Any) -> Any:
        machine_action_id = arguments["action_id"]

        url = urljoin(self.client.base_url, f"api/machineactions/{machine_action_id}")
        response = self.client.get(url)

        self.process_response(response)
        return response.json()
