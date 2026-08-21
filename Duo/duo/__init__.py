from enum import StrEnum

from sekoia_automation.module import Module

from .models import DuoModuleConfiguration


class DuoModule(Module):
    configuration: DuoModuleConfiguration


class LogType(StrEnum):
    ADMINISTRATION = "admin_log"
    AUTHENTICATION = "auth_log"
    TELEPHONY = "telephony_log"
    OFFLINE = "offline_log"
