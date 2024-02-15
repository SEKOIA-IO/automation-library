"""Module to work with Broadcom."""

from sekoia_automation.loguru.config import init_logging

from connectors import BroadcomCloudModule
from connectors.broadcom_cloud_swg_connector import BroadcomCloudSwgConnector

if __name__ == "__main__":
    init_logging()
    module = BroadcomCloudModule()
    module.register(BroadcomCloudSwgConnector, "broadcom_cloud_swg")
    module.run()
