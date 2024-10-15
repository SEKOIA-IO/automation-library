# coding: utf-8

from uuid import uuid4
import requests
from sekoia_automation.action import Action


class DownloadFileFromEndpointAction(Action):
    """
    Action to download a file from an HarfangLab endpoint
    """

    def run(self, arguments):
        agent_id = arguments["id"]
        path = arguments["path"]

        instance_url = self.module.configuration["url"]
        api_token = self.module.configuration["api_token"]

        # TODO: replace with a real call to HFL API
        # ... multipart ?
        response = requests.post(
            url=f"{instance_url}/download/stuff",
            json={"path": path, "agent_id": agent_id},
            headers={"Authorization": f"Token {api_token}"},
        )
        response.raise_for_status()

        # TODO: perhaps we can derive the filename from the response or the path, don't know...
        filename = str(uuid4())
        file_path = self._data_path / filename  # <- be sure you use self._data_path

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("wb") as f:
            f.write(response.content)

        return {"path": str(file_path)}
