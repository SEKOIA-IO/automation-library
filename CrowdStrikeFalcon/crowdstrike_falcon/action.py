from functools import cached_property

from sekoia_automation.action import Action

from crowdstrike_falcon import CrowdStrikeFalconModule
from crowdstrike_falcon.client import CrowdstrikeFalconClient


class CrowdstrikeAction(Action):
    module: CrowdStrikeFalconModule

    @cached_property
    def client(self):
        return CrowdstrikeFalconClient(
            self.module.configuration.base_url,
            self.module.configuration.client_id,
            self.module.configuration.client_secret,
            module_name=self.module.manifest.get("slug"),
            module_version=self.module.manifest.get("version"),
        )
