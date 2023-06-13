from sekoia_automation.module import Module

from tehtris_modules.models import TehtrisModuleConfiguration


class TehtrisModule(Module):
    configuration: TehtrisModuleConfiguration
