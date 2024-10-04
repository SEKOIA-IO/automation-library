from typing import Any

from sophos_module.action_sophos_edr_isolate import ActionSophosEDRIsolateEndpoint


class ActionSophosEDRDeIsolateEndpoint(ActionSophosEDRIsolateEndpoint):
    def run(self, arguments: dict[str, Any]) -> Any:
        endpoint_id = arguments["endpoint_id"]
        comment = arguments.get("comment")

        return self.set_isolation_status(endpoint_id=endpoint_id, enabled=False, comment=comment)
