from abc import ABC
from functools import cached_property

import requests
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
            self.log(message=raw["error"]["message"], level="error")
            logger.info(raw["error"]["message"], code=raw["error"]["code"], target=raw["error"]["target"])
