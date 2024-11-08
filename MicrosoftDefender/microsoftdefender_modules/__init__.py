from sekoia_automation.module import Module

from .models import MicrosoftDefenderModuleConfiguration


class MicrosoftDefenderModule(Module):
    configuration: MicrosoftDefenderModuleConfiguration
