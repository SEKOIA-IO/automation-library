from sekoia_automation.module import Module
from darktrace_modules.models import DarktraceModuleConfiguration
from enum import Enum


class DarktraceModule(Module):
    configuration: DarktraceModuleConfiguration


class Endpoints(Enum):
    MODEL_BREACHES = "modelbreaches"
    AI_ANALYST = "aianalyst/incidentevents"
