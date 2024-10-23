from typing import Any

from .action_base import MicrosoftDefenderBaseAction


class RestrictCodeExecutionAction(MicrosoftDefenderBaseAction):
    def run(self, arguments: Any) -> Any:
        return self.call_api(
            method="POST",
            url_path="api/machines/{machine_id}/restrictCodeExecution",
            args=arguments,
            arg_mapping={
                "comment": "Comment",
            },
        )
