from typing import Any

from sophos_module.action_base import SophosEDRAction


class ActionSophosEDRScan(SophosEDRAction):
    def run(self, arguments: dict[str, Any]) -> Any:
        endpoint_id = arguments["endpoint_id"]

        return self.call_endpoint(
            method="post", url=f"endpoint/v1/endpoints/{endpoint_id}/scans", data={}, use_region_url=True
        )
