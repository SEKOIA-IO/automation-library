from sekoia_automation.module import Module

from .models import BeyondTrustModuleConfiguration


class BeyondTrustModule(Module):
    configuration: BeyondTrustModuleConfiguration
