from abc import ABC
from functools import cached_property

from sekoia_automation.action import Action

from . import MicrosoftOutlookModule
from .client import ApiClient


class MicrosoftGraphActionBase(Action, ABC):
    module: MicrosoftOutlookModule

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            tenant_id=self.module.configuration.tenant_id,
            app_id=self.module.configuration.client_id,
            app_secret=self.module.configuration.client_secret,
        )
