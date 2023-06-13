from posixpath import join as urljoin

import requests
from requests import Response
from sekoia_automation.action import Action


class IKnowIPExistAction(Action):
    """
    Action to fast check if IP adress can be found in IKnowChatYouDownload database
    """

    def run(self, arguments) -> dict:
        url: str = self.module.configuration["host"]

        get_url: str = urljoin(url, "history/exist")
        params: dict = {
            "key": self.module.configuration.get("key"),
            "ip": arguments["ip"],
        }

        # Fetch the report
        response: Response = requests.get(get_url, params=params)
        response.raise_for_status()

        report = response.json()

        if report.get("exists"):
            self.set_output("known", True)
        else:
            self.set_output("unknown", True)

        return report
