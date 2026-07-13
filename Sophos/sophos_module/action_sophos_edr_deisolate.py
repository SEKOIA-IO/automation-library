from typing import Any

from sophos_module.action_sophos_edr_isolate import ActionSophosEDRIsolateEndpoint, SophosEndpointIsolationArguments


class ActionSophosEDRDeIsolateEndpoint(ActionSophosEDRIsolateEndpoint):
    def run(self, arguments: SophosEndpointIsolationArguments) -> Any:
        return self.set_isolation_status(
            endpoint_id=str(arguments.endpoint_id), enabled=False, comment=arguments.comment
        )
