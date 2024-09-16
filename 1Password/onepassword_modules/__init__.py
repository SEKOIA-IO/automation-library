from sekoia_automation.module import Module

from .models import OnePasswordModuleConfiguration


class OnePasswordModule(Module):
    configuration: OnePasswordModuleConfiguration
