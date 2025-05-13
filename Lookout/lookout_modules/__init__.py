from sekoia_automation.module import Module

from .models import LookoutModuleConfiguration


class LookoutModule(Module):
    configuration: LookoutModuleConfiguration
