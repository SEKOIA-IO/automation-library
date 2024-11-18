from typing import Any

from .action_base import MicrosoftDefenderBaseAction


class CancelMachineAction(MicrosoftDefenderBaseAction):
    def run(self, arguments: Any) -> Any:
        return self.call_api(
            method="POST",
            url_path="/api/machineactions/{action_id}/cancel",
            args=arguments,
            arg_mapping={"comment": "Comment"},
        )
