from typing import Any

from sophos_module.action_base import SophosEDRAction
from sophos_module.base import SophosEndpointArguments


class ActionSophosEDRScan(SophosEDRAction):
    def run(self, arguments: SophosEndpointArguments) -> Any:
        return self.call_endpoint(
            method="post",
            url=f"endpoint/v1/endpoints/{str(arguments.endpoint_id)}/scans",
            data={},
            use_region_url=True,
        )
