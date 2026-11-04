from sekoia_automation.module import Module
from sekoia_formatter_modules.models import SekoiaFormatterModuleConfiguration


class SekoiaFormatterModule(Module):
    configuration: SekoiaFormatterModuleConfiguration
