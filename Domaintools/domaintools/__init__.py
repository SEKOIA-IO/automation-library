from sekoia_automation.module import Module
from domaintools_modules.models import DomaintoolsModuleConfiguration


class DomaintoolsModule(Module):
    configuration: DomaintoolsModuleConfiguration
