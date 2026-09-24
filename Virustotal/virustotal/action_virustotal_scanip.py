from posixpath import join as urljoin

import requests
from pydantic import BaseModel, Field, IPvAnyAddress
from requests import Response
from sekoia_automation.action import Action


class VirusTotalScanIPArguments(BaseModel):
    ip: IPvAnyAddress = Field(..., description="IP address to scan")


class VirusTotalScanIPAction(Action):
    """
    Action to scan an IP with VirusTotal
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, arguments: VirusTotalScanIPArguments) -> dict | None:
        ip_value = str(arguments.ip)

        url: str = "https://www.virustotal.com/vtapi/v2/"
        get_url: str = urljoin(url, "ip-address/report")
        params: dict = {
            "apikey": self.module.configuration.get("apikey"),
            "ip": ip_value,
        }

        # Get IP report from Virus Total
        response: Response = requests.get(get_url, params=params)
        response.raise_for_status()

        return response.json()
