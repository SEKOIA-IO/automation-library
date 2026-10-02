from .connector_ubika_cloud_protector_next_gen_base import (
    UbikaCloudProtectorNextGenBaseConnector,
    UbikaCloudProtectorNextGenBaseConnectorConfiguration,
)


class UbikaCloudProtectorNextGenAlertsConnector(UbikaCloudProtectorNextGenBaseConnector):
    NAME: str = "Ubika Cloud Protector NextGen Alerts"
    configuration: UbikaCloudProtectorNextGenBaseConnectorConfiguration
    cache_size: int = 1000
    endpoint: str = "security-events"

    def get_event_id(self, event: dict) -> str | None:
        """Extract the unique event ID from an alert event."""
        event_id = event.get("logAlertUid")
        if event_id is None:
            return None
        return str(event_id)
