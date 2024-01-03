from posixpath import join as urljoin

import requests
from requests import Response
from sekoia_automation.action import Action


class IKnowIPHistoryAction(Action):
    """
    Action to fetch the Torrent history of a specified IP
    """

    def run(self, arguments) -> dict:
        url: str = self.module.configuration["host"]

        get_url: str = urljoin(url, "history/peer/")
        params: dict = {
            "key": self.module.configuration.get("key"),
            "ip": arguments["ip"],
        }

        # Fetch the report
        response: Response = requests.get(get_url, params=params)
        response.raise_for_status()

        return response.json()
