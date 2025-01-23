from sekoia_automation.module import Module

from .models import EsetModuleConfiguration


class EsetModule(Module):
    configuration: EsetModuleConfiguration
