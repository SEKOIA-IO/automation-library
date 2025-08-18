from abc import ABC
from functools import cached_property
from typing import Any

import requests
from sekoia_automation.action import Action

from . import TrendMicroVisionOneModule
from .client import TrendMicroVisionOneApiClient


class TrendMicroVisionOneBaseAction(Action, ABC):
    module: TrendMicroVisionOneModule

    @cached_property
    def client(self) -> TrendMicroVisionOneApiClient:
        return TrendMicroVisionOneApiClient(api_key=self.module.configuration.api_key)

    def process_response(self, response: requests.Response, headers_to_include: list[str] | None = None) -> Any:
        if headers_to_include is None:
            headers_to_include = []

        # not logged in
        if response.status_code == 401:
            self.log("The credential provided are invalid", level="critical")

        status = response.status_code
        headers = [
            {"name": name, "value": value} for name, value in response.headers.items() if name in headers_to_include
        ]
        if "application/json" in response.headers.get("Content-Type", ""):
            body = response.json()
            if isinstance(body, list):
                # multiple responses - wrap as dict
                return {"result": body}

        else:
            body = response.text

        return {"status": status, "headers": headers, "body": body}
