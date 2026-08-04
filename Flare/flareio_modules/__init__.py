from sekoia_automation.module import Module

from flareio_modules.models import FlareIOModuleConfiguration


class FlareIOModule(Module):
    configuration: FlareIOModuleConfiguration
