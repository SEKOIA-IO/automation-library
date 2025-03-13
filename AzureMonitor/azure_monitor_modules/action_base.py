from abc import ABC
from functools import cached_property

from azure.identity import ClientSecretCredential
from azure.monitor.query import LogsQueryClient
from sekoia_automation.action import Action

from . import AzureMonitorModule


class AzureMonitorBaseAction(Action, ABC):
    module: AzureMonitorModule

    @cached_property
    def client(self):
        credentials = ClientSecretCredential(
            tenant_id=self.module.configuration.tenant_id,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
        )
        return LogsQueryClient(credentials)
