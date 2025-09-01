from sekoia_automation.module import Module

from .models import TrendMicroVisionOneModuleConfiguration


class TrendMicroVisionOneModule(Module):
    configuration: TrendMicroVisionOneModuleConfiguration
