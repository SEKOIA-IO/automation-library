from sekoia_automation.module import Module

from .models import AnozrwayModuleConfiguration


class AnozrwayModule(Module):
    name = "Anozrway"
    description = "Anozrway provides domain-based breach and leak intelligence through a secured API."
    configuration: AnozrwayModuleConfiguration
