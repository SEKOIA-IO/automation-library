from sekoia_automation.module import Module

from .models import ZimperiumModuleConfiguration


class ZimperiumModule(Module):
    configuration: ZimperiumModuleConfiguration
