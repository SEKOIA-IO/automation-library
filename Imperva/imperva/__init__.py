from sekoia_automation.module import Module

from .models import ImpervaModuleConfiguration


class ImpervaModule(Module):
    configuration: ImpervaModuleConfiguration
