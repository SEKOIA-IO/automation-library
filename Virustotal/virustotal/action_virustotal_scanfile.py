import os
import time
from posixpath import join as urljoin

import requests
from requests import Response
from sekoia_automation.action import Action

from virustotal.errors import MaxFileSizeExceedError, RequestLimitError
from virustotal.utils import virustotal_detection_outputs


class VirusTotalScanFileAction(Action):
    """
    Action to scan a file with VirusTotal
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, arguments) -> dict:
        url: str = "https://www.virustotal.com/vtapi/v2/"
        upload_url: str = urljoin(url, "file/scan")
        params: dict = {"apikey": self.module.configuration.get("apikey")}
        files: dict = {"file": (arguments["file"], open(arguments["file"], "rb").read())}

        file_size = os.path.getsize(arguments["file"])

        if file_size >= 200000000:
            raise MaxFileSizeExceedError(msg=f"The file to send exceed the maximum size of 200MB ({file_size})")

        response: Response

        if file_size >= 32000000:
            response = requests.get(urljoin(url, "file/scan/upload_url"), params=params)
            response.raise_for_status()
            upload_url = response.json()["upload_url"]

        # Send file to Virus Total
        response = requests.post(upload_url, files=files, params=params)
        response.raise_for_status()

        vt_response = response.json()
        return_code: int = -2
        count_error: int = 0

        while return_code == -2:
            time.sleep((2**count_error) * 30)
            response = requests.get(
                urljoin(url, "file/report") + f"?apikey={params['apikey']}&resource={vt_response['scan_id']}"
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
