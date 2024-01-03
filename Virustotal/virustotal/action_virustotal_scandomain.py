from posixpath import join as urljoin

import requests
from requests import Response
from sekoia_automation.action import Action


class VirusTotalScanDomainAction(Action):
    """
    Action to scan an Domain with VirusTotal
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, arguments) -> dict:
        url: str = "https://www.virustotal.com/vtapi/v2/"
        get_url: str = urljoin(url, "domain/report")
        params: dict = {
            "apikey": self.module.configuration.get("apikey"),
            "domain": arguments["domain"],
        }

        # Get Domain report from Virus Total
        response: Response = requests.get(get_url, params=params)
        response.raise_for_status()

        return response.json()
