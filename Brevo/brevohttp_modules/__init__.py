from sekoia_automation.module import Module
from brevohttp_modules.models import BrevoHttpModuleConfiguration


class BrevoHttpModule(Module):
    configuration: BrevoHttpModuleConfiguration
