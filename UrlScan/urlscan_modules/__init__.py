from sekoia_automation.module import Module

from urlscan_modules.models import UrlScanModuleConfiguration


class UrlScanModule(Module):
    configuration: UrlScanModuleConfiguration
