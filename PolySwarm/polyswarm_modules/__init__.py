from sekoia_automation.module import Module

from polyswarm_modules.models import PolyswarmModuleConfiguration


class PolyswarmModule(Module):
    configuration: PolyswarmModuleConfiguration
