from sekoia_automation.module import Module

from .models import MicrosoftOutlookModuleConfiguration


class MicrosoftOutlookModule(Module):
    """Represent the Microsoft Outlook automation module."""

    configuration: MicrosoftOutlookModuleConfiguration
