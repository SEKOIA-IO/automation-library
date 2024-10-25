from typing import Any
from urllib.parse import urljoin

from .action_base import MicrosoftDefenderBaseAction


class UpdateAlertAction(MicrosoftDefenderBaseAction):
    def run(self, arguments: Any) -> Any:
        return self.call_api(
            method="PATCH",
            url_path="api/alerts/{alert_id}/",
            args=arguments,
            arg_mapping={
                "comment": "Comment",
                "status": "Status",
                "classification": "Classification",
                "owner": "assignedTo",
                "determination": "Determination",
            },
        )
