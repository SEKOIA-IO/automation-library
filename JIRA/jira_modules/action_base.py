from abc import abstractmethod
from functools import cached_property
from typing import Any

import requests
from sekoia_automation.action import Action

from .base import JIRAModule
from .client import ApiClient


class JIRAAction(Action):
    module: JIRAModule

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(email=self.module.configuration.email, api_key=self.module.configuration.api_key)

    @cached_property
    def base_url(self) -> str:
        return "https://%s" % self.module.configuration.domain.replace("https://", "").replace("http://", "")

    def get_json(self, path: str, **kwargs) -> Any:
        response = self.client.get(f"{self.base_url}/rest/api/3/{path}", timeout=60, **kwargs)
        self._handle_response_error(response)
        return response.json() if len(response.content) > 0 else None

    def post_json(self, path: str, **kwargs) -> Any:
        response = self.client.post(f"{self.base_url}/rest/api/3/{path}", timeout=60, **kwargs)
        self._handle_response_error(response)
        return response.json() if len(response.content) > 0 else None

    def get_paginated_results(self, path: str, result_field: str | None = "values") -> list:
        start_at = 0
        max_results = 50

        response = self.get_json(path=path, params={"maxResults": max_results, "startAt": start_at})
        is_last = response.get("isLast") if type(response) == dict else False
        if is_last:
            return response.get(result_field) if result_field else response

        result = []
        while True:
            items = response.get(result_field) if result_field else response

            if len(items) == 0:
                break

            result.extend(items)
            start_at += max_results
            response = self.get_json(path=path, params={"maxResults": max_results, "startAt": start_at})

        return result

    def _handle_response_error(self, response: requests.Response):
        if not response.ok:
            message = f"Request to JIRA API failed with status {response.status_code} - {response.reason}"
            if response.status_code == 400:
                data = response.json()
                detailed_errors = data.get("errorMessages", [response.text])
                message = f"{message}: \n {','.join(detailed_errors)}"

            self.log(message=message, level="error")
            response.raise_for_status()

    @abstractmethod
    def run(self, arguments: Any) -> Any:
        raise NotImplementedError
