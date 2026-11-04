from sekoia_automation.module import Module

from .models import (
    MicrosoftSentinelConfiguration,
    MicrosoftSentinelConnectorConfiguration,  # noqa: F401
    MicrosoftSentinelResponseModel,  # noqa: F401
)


class MicrosoftSentinelModule(Module):
    configuration: MicrosoftSentinelConfiguration  # type: ignore[override]
