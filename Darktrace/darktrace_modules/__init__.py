from sekoia_automation.module import Module

from darktrace_modules.models import DarktraceModuleConfiguration


class DarktraceModule(Module):
    configuration: DarktraceModuleConfiguration
