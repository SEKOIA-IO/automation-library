from typing import Any
from urllib.parse import urljoin

from .action_base import MicrosoftDefenderBaseAction


class ScanMachineAction(MicrosoftDefenderBaseAction):
    def run(self, arguments: Any) -> Any:
        machine_id = arguments["machine_id"]
        comment = arguments["comment"]
        scan_type = arguments["scan_type"]  # Full/Quick

        url = urljoin(self.client.base_url, f"api/machines/{machine_id}/runAntiVirusScan")
        response = self.client.post(url, json={"Comment": comment, "ScanType": scan_type})
        self.process_response(response)
        return response.json()
