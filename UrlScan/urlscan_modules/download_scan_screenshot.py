from typing import Any

from urlscan import APIError, Client

from urlscan_modules.artefacts import PNG_SIGNATURE, write_screenshot
from urlscan_modules.base import ActionError, UrlScanAction
from urlscan_modules.validators import valid_scan_id


class DownloadScanScreenshot(UrlScanAction):
    def perform(self, client: Client, arguments: dict[str, Any]) -> dict[str, Any]:
        scan_id = valid_scan_id(arguments.get("scan_id"))
        try:
            screenshot = self.call(client.get_screenshot, scan_id)
        except APIError as error:
            if error.status == 404:
                raise ActionError(
                    f"Screenshot of scan {scan_id} was not stored by urlscan.io "
                    "(or the scan is unknown or not finished)"
                ) from error
            raise

        content = screenshot.getvalue()
        if not content.startswith(PNG_SIGNATURE):
            raise ActionError(f"urlscan.io returned an invalid screenshot for scan {scan_id}")

        return {
            "screenshot_path": write_screenshot(self.data_path, scan_id, content),
            "screenshot_url": f"{self.base_url}/screenshots/{scan_id}.png",
            "size": len(content),
        }
