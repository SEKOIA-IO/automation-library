import time
from posixpath import join as urljoin

import requests
from requests import Response
from sekoia_automation.action import Action

from virustotal.errors import RequestLimitError
from virustotal.utils import virustotal_detection_outputs


class VirusTotalScanURLAction(Action):
    """
    Action to scan an URL with VirusTotal
    """

    sleep_multiplier = 30

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, arguments) -> dict:
        url: str = "https://www.virustotal.com/vtapi/v2/"
        get_url: str = urljoin(url, "url/report")
        params: dict = {
            "apikey": self.module.configuration.get("apikey"),
            "resource": arguments["url"],
            "scan": 1,
        }

        # Get URL report from Virus Total or scan it if it does not exists yet
        response: Response = requests.get(get_url, params=params)
        response.raise_for_status()

        if response.status_code == 204:
            vt_response = {}
        else:
            vt_response = response.json()

        if not vt_response.get("scans"):
            return_code: int = -2
            count_error: int = 0

            while return_code == -2:
                time.sleep((2**count_error) * self.sleep_multiplier)
                response = requests.get(
                    get_url,
                    params={"apikey": params["apikey"], "resource": arguments["url"]},
                )
                if response.status_code == 200:
                    count_error = 0

                if response.status_code == 204:
                    count_error += 1

                    if count_error >= 5:
                        raise RequestLimitError()

                    continue

                response.raise_for_status()
                vt_response = response.json()
                return_code = vt_response["response_code"]

        virustotal_detection_outputs(
            action=self,
            vt_response=vt_response,
            threshold=arguments.get("detect_threshold", 1),
        )

        return vt_response
