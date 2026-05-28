from sekoia_automation.module import Module
from locaterisk_modules.models import LocateRiskModuleConfiguration


class LocateRiskModule(Module):
    configuration: LocateRiskModuleConfiguration
