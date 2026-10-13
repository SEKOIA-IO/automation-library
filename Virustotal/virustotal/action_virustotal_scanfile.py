import os
import time
from posixpath import join as urljoin

import requests
from pydantic import AliasChoices, BaseModel, Field
from requests import Response
from sekoia_automation.action import Action

from virustotal.errors import FileScanError, MaxFileSizeExceedError, RequestLimitError
from virustotal.utils import virustotal_detection_outputs


class VirusTotalScanFileArguments(BaseModel):
    file: str = Field(..., min_length=1, description="Path of the file to scan")
    detect_threshold: int = Field(
        default=1,
        validation_alias=AliasChoices("detect_threshold", "detect_treshold"),
        description="Number of positives to consider the file detected",
    )


class VirusTotalScanFileAction(Action):
    """
    Action to scan a file with VirusTotal
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, arguments: VirusTotalScanFileArguments) -> dict:
        file_path = arguments.file

        url: str = "https://www.virustotal.com/vtapi/v2/"
        upload_url: str = urljoin(url, "file/scan")
        params: dict = {"apikey": self.module.configuration.get("apikey")}
        files: dict = {"file": (file_path, open(file_path, "rb").read())}

        file_size = os.path.getsize(file_path)

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
        scan_id = vt_response.get("scan_id")
        if not scan_id:
            raise FileScanError(msg=f"The file upload failed: {vt_response.get('verbose_msg', 'no scan id returned')}")

        return_code: int | None = -2
        count_error: int = 0

        while return_code == -2:
            time.sleep((2**count_error) * 30)
            response = requests.get(urljoin(url, "file/report") + f"?apikey={params['apikey']}&resource={scan_id}")
            if response.status_code == 200:
                count_error = 0

            if response.status_code == 204:
                count_error += 1

                if count_error >= 5:
                    raise RequestLimitError()

                continue

            response.raise_for_status()
            vt_response = response.json()
            return_code = vt_response.get("response_code")

        if return_code != 1:
            raise FileScanError(
                msg=f"The scan report is not available: {vt_response.get('verbose_msg', 'unexpected response')}"
            )

        virustotal_detection_outputs(
            action=self,
            vt_response=vt_response,
            threshold=arguments.detect_threshold,
        )

        return vt_response
