from abc import ABC
from functools import cached_property

from requests import Response
from sekoia_automation.action import Action

from . import MicrosoftOutlookModule
from .client import ApiClient


class GraphAPIException(Exception):
    pass


class MicrosoftGraphActionBase(Action, ABC):
    module: MicrosoftOutlookModule

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            tenant_id=self.module.configuration.tenant_id,
            app_id=self.module.configuration.client_id,
            app_secret=self.module.configuration.client_secret,
        )

    def handle_response(self, response: Response) -> None:
        if not response.ok:
            message = f"Request to Microsoft Graph API failed with status {response.status_code} - {response.reason}"
            if response.status_code == 400:
                message = response.text
                self.log(message=message, level="error")
                raise GraphAPIException(message)

            self.log(message=message, level="error")
            response.raise_for_status()
