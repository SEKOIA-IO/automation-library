from enum import Enum

from sekoia_automation.module import Module

from .models import DuoModuleConfiguration


class DuoModule(Module):
    configuration: DuoModuleConfiguration


class LogType(str, Enum):
    ADMINISTRATION = "admin_log"
    AUTHENTICATION = "auth_log"
    TELEPHONY = "telephony_log"
    OFFLINE = "offline_log"
