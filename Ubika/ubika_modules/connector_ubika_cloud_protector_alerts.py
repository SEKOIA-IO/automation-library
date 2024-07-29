from . import UbikaModule
from .connector_ubika_cloud_protector_base import (
    UbikaCloudProtectorBaseConnector,
    UbikaCloudProtectorConnectorConfiguration,
)


class UbikaCloudProtectorAlertsConnector(UbikaCloudProtectorBaseConnector):
    module: UbikaModule
    configuration: UbikaCloudProtectorConnectorConfiguration

    NAME = "Ubika Cloud Protector Alerts"

    def generate_endpoint_url(self) -> str:
        return f"{self.BASE_URI}/providers/{self.configuration.provider}/tenants/{self.configuration.tenant}/alertlogs"
