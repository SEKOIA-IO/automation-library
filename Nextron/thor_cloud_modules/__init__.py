from sekoia_automation.module import Module

from thor_cloud_modules.connector import ThorCloudConnector
from thor_cloud_modules.models import ThorCloudModuleConfiguration


class ThorCloudModule(Module):
    configuration: ThorCloudModuleConfiguration


__all__ = ["ThorCloudModule", "ThorCloudConnector"]
