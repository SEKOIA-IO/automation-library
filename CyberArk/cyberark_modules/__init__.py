from sekoia_automation.module import Module

from .models import CyberArkModuleConfiguration


class CyberArkModule(Module):
    configuration: CyberArkModuleConfiguration
