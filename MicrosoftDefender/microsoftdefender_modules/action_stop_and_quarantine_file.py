from typing import Any
from urllib.parse import urljoin

from .action_base import MicrosoftDefenderBaseAction


class StopAndQuarantineFileAction(MicrosoftDefenderBaseAction):
    def run(self, arguments: Any) -> Any:
        machine_id = arguments["machine_id"]
        comment = arguments["comment"]
        file_sha1 = arguments["sha1"]

        data = {"Comment": comment, "Sha1": file_sha1}

        url = urljoin(self.client.base_url, f"api/machines/{machine_id}/StopAndQuarantineFile")
        response = self.client.post(url, json=data)

        self.process_response(response)
        return response.json()
