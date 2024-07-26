from sekoia_automation.module import Module

from thinkst_canary_modules.models import ThinkstCanaryModuleConfiguration


class ThinkstCanaryModule(Module):
    configuration: ThinkstCanaryModuleConfiguration
