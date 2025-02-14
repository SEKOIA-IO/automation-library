from sekoia_automation.module import Module

from .models import (
    MicrosoftSentinelConfiguration,
    MicrosoftSentinelResponseModel,
    MicrosoftSentinelConnectorConfiguration,
)


class MicrosoftSentinelModule(Module):
    configuration: MicrosoftSentinelConfiguration
