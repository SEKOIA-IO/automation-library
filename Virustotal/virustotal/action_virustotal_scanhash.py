from posixpath import join as urljoin

import requests
from sekoia_automation.action import Action

from virustotal.utils import virustotal_detection_outputs


class VirusTotalScanHashAction(Action):
    """
    Action to scan a hash with VirusTotal
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, arguments) -> dict:
        url: str = "https://www.virustotal.com/vtapi/v2/"
        params: dict = {"apikey": self.module.configuration.get("apikey")}

        response = requests.get(
            urljoin(url, "file/report") + f"?apikey={params['apikey']}&resource={arguments['hash']}"
        )
        response.raise_for_status()
        vt_response: dict = response.json()

        if vt_response["response_code"] == 0:
            self.set_output("unknown", True)

        elif vt_response["response_code"] == 1:
            virustotal_detection_outputs(
                action=self,
                vt_response=vt_response,
                threshold=arguments.get("detect_threshold", 1),
            )

        return vt_response
