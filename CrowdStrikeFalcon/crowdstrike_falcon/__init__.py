from sekoia_automation.module import Module

from crowdstrike_falcon.models import CrowdStrikeFalconModuleConfiguration


class CrowdStrikeFalconModule(Module):
    configuration: CrowdStrikeFalconModuleConfiguration
