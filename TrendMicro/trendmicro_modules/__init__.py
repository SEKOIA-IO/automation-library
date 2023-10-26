from sekoia_automation.module import Module

from .models import TrendMicroModuleConfiguration


class TrendMicroModule(Module):
    configuration: TrendMicroModuleConfiguration
