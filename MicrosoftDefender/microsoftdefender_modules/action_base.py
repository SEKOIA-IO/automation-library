from abc import ABC
from functools import cached_property
from typing import Any
from urllib.parse import urljoin

import requests
from requests import Response
from sekoia_automation.action import Action

from . import MicrosoftDefenderModule
from .client import ApiClient
from .logging import get_logger

logger = get_logger()


class MicrosoftDefenderBaseAction(Action, ABC):
    module: MicrosoftDefenderModule

    @cached_property
    def client(self):
        return ApiClient(
            base_url=self.module.configuration.base_url,
            app_id=self.module.configuration.app_id,
            app_secret=self.module.configuration.app_secret,
            tenant_id=self.module.configuration.tenant_id,
        )

    def process_response(self, response: requests.Response) -> None:
        raw = response.json()
        if not response.ok:
            self.error(message=raw["error"]["message"])
            logger.info(raw["error"]["message"], code=raw["error"]["code"], target=raw["error"]["target"])

    def call_api(self, method: str, url_path: str, args: dict[str, Any], arg_mapping: dict[str, str]) -> Response:
        formatted_url = url_path.format(**args)  # allows substitution in URL
        url = urljoin(self.client.base_url, formatted_url)

        data = {}
        for arg_name, arg_value in args.items():
            data_name = arg_mapping.get(arg_name)
            if data_name:
                data[data_name] = arg_value

        if method.lower() == "post":
            response = self.client.post(url, json=data)

        elif method.lower() == "patch":
            response = self.client.patch(url, json=data)

        else:
            response = self.client.get(url, json=data)

        self.process_response(response)
        return response.json()
