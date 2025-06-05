from sekoia_automation.module import Module
from xsiam.models import XsiamModuleConfiguration


class XsiamModule(Module):
    configuration: XsiamModuleConfiguration
