from sekoia_automation.module import Module

from new_relic_modules.models import NewRelicModuleConfiguration


class NewRelicModule(Module):
    configuration: NewRelicModuleConfiguration
