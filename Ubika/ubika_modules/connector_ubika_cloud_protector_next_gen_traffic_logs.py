from datetime import datetime

from .connector_ubika_cloud_protector_next_gen_base import (
    UbikaCloudProtectorNextGenBaseConnector,
    UbikaCloudProtectorNextGenBaseConnectorConfiguration,
)


class UbikaCloudProtectorNextGenTrafficLogsConnectorConfiguration(
    UbikaCloudProtectorNextGenBaseConnectorConfiguration
):
    pass


class UbikaCloudProtectorNextGenTrafficLogsConnector(UbikaCloudProtectorNextGenBaseConnector):
    """
    Connector that continuously polls the Ubika Cloud Protector NextGen
    traffic-logs endpoint and forwards them to the configured intake.
    Uses TimeStepper to manage time ranges.
    """

    NAME: str = "Ubika Cloud Protector NextGen Traffic Logs"
    configuration: UbikaCloudProtectorNextGenTrafficLogsConnectorConfiguration
    cache_size: int = 10000
    endpoint: str = "traffic-logs"

    def get_event_id(self, event: dict) -> str | None:
        """Extract the unique event ID from a traffic log event."""
        request = event.get("request") or {}
        uid = request.get("uid")
        if uid is None:
            return None
        return str(uid)
