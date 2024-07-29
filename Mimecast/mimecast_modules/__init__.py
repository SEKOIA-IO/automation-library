from sekoia_automation.module import Module

from .models import MimecastModuleConfiguration


class MimecastModule(Module):
    configuration: MimecastModuleConfiguration
