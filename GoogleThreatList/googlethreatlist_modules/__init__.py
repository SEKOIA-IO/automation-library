from sekoia_automation.module import Module
from googlethreatlist_modules.models import GooglethreatlistModuleConfiguration


class GooglethreatlistModule(Module):
    configuration: GooglethreatlistModuleConfiguration
