from sekoia_automation.module import Module

from jumpcloud_modules.models import JumpcloudDirectoryInsightsModuleConfiguration


class JumpcloudDirectoryInsightsModule(Module):
    configuration: JumpcloudDirectoryInsightsModuleConfiguration
