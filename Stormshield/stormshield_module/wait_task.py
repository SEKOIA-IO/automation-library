import requests
from requests import Response

from stormshield_module.base import StormshieldAction
from stormshield_module.exceptions import RemoteTaskExecutionFailedError


class WaitForTaskCompletionAction(StormshieldAction):
    verb = "get"
    endpoint = "/agents/tasks/{task_id}"
    query_parameters: list[str] = []

    def get_response(self, url, body, headers) -> Response:
        result = requests.request(self.verb, url, json=body, headers=headers, timeout=self.timeout)
        execution_state = result.json()["status"]

        if execution_state.lower() == "succeeded":
            return result
        elif execution_state.lower() == "failed":
            raise RemoteTaskExecutionFailedError(result.json()["errorMessage"])
