from sekoia_automation.module import Module

from .models import UbikaModuleConfiguration


class UbikaModule(Module):
    configuration: UbikaModuleConfiguration
