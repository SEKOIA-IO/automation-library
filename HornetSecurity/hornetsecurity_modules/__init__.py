from sekoia_automation.module import Module
from hornetsecurity_modules.models import HornetsecurityModuleConfiguration


class HornetsecurityModule(Module):
    configuration: HornetsecurityModuleConfiguration
