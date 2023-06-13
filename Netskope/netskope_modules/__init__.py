from sekoia_automation.module import Module

from netskope_modules.models import NetskopeModuleConfiguration


class NetskopeModule(Module):
    configuration: NetskopeModuleConfiguration
