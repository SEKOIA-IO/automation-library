from sekoia_automation.module import Module

from .models import MicrosoftOutlookModuleConfiguration


class MicrosoftOutlookModule(Module):
    configuration: MicrosoftOutlookModuleConfiguration
