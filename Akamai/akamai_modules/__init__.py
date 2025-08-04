from sekoia_automation.module import Module

from .models import AkamaiModuleConfiguration


class AkamaiModule(Module):
    configuration: AkamaiModuleConfiguration
