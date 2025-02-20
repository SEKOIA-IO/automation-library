import requests
from requests import Response
from typing import Any

from stormshield_module.base import StormshieldAction
from stormshield_module.exceptions import RemoteTaskExecutionFailedError


class WaitForTaskCompletionAction(StormshieldAction):
    verb = "get"
    endpoint = "/agents/tasks/{task_id}"
    query_parameters: list[str] = []

    def get_response(self, url: str, body: dict[str, Any] | None, headers: dict[str, Any], verify: bool) -> Response:
        result = requests.request(self.verb, url, json=body, headers=headers, timeout=self.timeout, verify=verify)
        content = result.json()

        if content.get("errorCode"):
            raise Exception(f"Error {content['errorCode']}: {content['errorMessage']}")

        execution_state = content["status"]

        if execution_state.lower() == "failed":
            raise RemoteTaskExecutionFailedError(content["errorMessage"])

        return result
