import requests
from requests import Response
from typing import Any

from stormshield_module.base import StormshieldAction


class WaitForTaskCompletionAction(StormshieldAction):
    verb = "get"
    endpoint = "/agents/tasks/{task_id}"
    query_parameters: list[str] = []
