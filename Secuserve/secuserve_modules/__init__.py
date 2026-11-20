from sekoia_automation.module import Module

from secuserve_modules.models import SecuserveModuleConfiguration


class SecuserveModule(Module):
    configuration: SecuserveModuleConfiguration
