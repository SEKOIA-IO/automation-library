from typing import Any
from urllib.parse import urljoin

from .action_base import MicrosoftDefenderBaseAction


class IsolateMachineAction(MicrosoftDefenderBaseAction):
    def run(self, arguments: Any) -> Any:
        machine_id = arguments["machine_id"]
        comment = arguments["comment"]
        isolation_type = arguments.get("isolation_type")  # Full/Selective

        data = {"Comment": comment}
        if isolation_type:
            data["IsolationType"] = isolation_type

        url = urljoin(self.client.base_url, f"api/machines/{machine_id}/isolate")
        response = self.client.post(url, json=data)

        self.process_response(response)
        return response.json()
