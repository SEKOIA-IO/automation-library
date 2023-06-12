from sekoia_automation.module import Module

from cybereason_modules.models import CybereasonModuleConfiguration


class CybereasonModule(Module):
    configuration: CybereasonModuleConfiguration
