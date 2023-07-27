from sekoia_automation.module import Module

from .models import VadeCloudModuleConfiguration


class VadeCloudModule(Module):
    configuration: VadeCloudModuleConfiguration
