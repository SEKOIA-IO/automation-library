from sekoia_automation.module import Module

from vadesecure_modules.models import VadeSecureConfiguration


class VadeSecureModule(Module):
    configuration: VadeSecureConfiguration
