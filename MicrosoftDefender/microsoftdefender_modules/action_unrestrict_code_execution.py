from typing import Any
from urllib.parse import urljoin

from .action_base import MicrosoftDefenderBaseAction


class UnRestrictCodeExecutionAction(MicrosoftDefenderBaseAction):
    def run(self, arguments: Any) -> Any:
        machine_id = arguments["machine_id"]
        comment = arguments["comment"]

        url = urljoin(self.client.base_url, f"api/machines/{machine_id}/unrestrictCodeExecution")
        response = self.client.post(url, json={"Comment": comment})
        self.process_response(response)

        return response.json()
