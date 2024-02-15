from sekoia_automation.module import Module

from .models import ExtraHopModuleConfiguration


class ExtraHopModule(Module):
    configuration: ExtraHopModuleConfiguration
