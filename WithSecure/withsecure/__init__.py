from sekoia_automation.module import Module

from withsecure.models import WithSecureModuleConfiguration


class WithSecureModule(Module):
    configuration: WithSecureModuleConfiguration
