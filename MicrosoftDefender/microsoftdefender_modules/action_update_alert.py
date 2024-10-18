from typing import Any
from urllib.parse import urljoin

from .action_base import MicrosoftDefenderBaseAction


class UpdateAlertAction(MicrosoftDefenderBaseAction):
    def run(self, arguments: Any) -> Any:
        alert_id = arguments["alert_id"]
        comment = arguments.get("comment")
        status = arguments.get("status")  # New, InProgress, Resolved
        classification = arguments.get("classification")  # TruePositive, FalsePositive, InformationalExpectedActivity
        determination = arguments.get("determination")
        owner = arguments.get("owner")

        data = {}
        if comment:
            data["comment"] = comment

        if status:
            data["status"] = status

        if classification:
            data["classification"] = classification

        if owner:
            data["assignedTo"] = owner

        if determination:
            data["determination"] = determination

        url = urljoin(self.client.base_url, f"api/alerts/{alert_id}/")
        response = self.client.patch(url, json=data)

        self.process_response(response)
        return response.json()
