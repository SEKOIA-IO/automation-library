from urllib.parse import urljoin

from action_base import SophosEDRAction

from .logging import get_logger

logger = get_logger()


class ActionSophosEDRScan(SophosEDRAction):
    def run(self, arguments: dict) -> dict:
        endpoint_id = arguments["endpoint_id"]

        return self.call_endpoint(
            method="post", url=f"endpoint/v1/endpoints/{endpoint_id}/scans", data={}, use_region_url=True
        )
