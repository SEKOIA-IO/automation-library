from typing import Any

from .action_base import MicrosoftDefenderBaseAction


class GetMachineAction(MicrosoftDefenderBaseAction):
    def run(self, arguments: Any) -> Any:
        return self.call_api(method="GET", url_path="api/machineactions/{action_id}", args=arguments, arg_mapping={})
