from sekoia_automation.module import Module

from .models import AzureMonitorModuleConfiguration


class AzureMonitorModule(Module):
    configuration: AzureMonitorModuleConfiguration
