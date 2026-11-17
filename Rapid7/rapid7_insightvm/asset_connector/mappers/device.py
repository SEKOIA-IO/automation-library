from sekoia_automation.asset_connector.models.ocsf.device import Device, DeviceTypeId, DeviceTypeStr
from sekoia_automation_models.hostname import split_hostname

from rapid7_insightvm.asset_connector.models import Rapid7Asset

ASSET_TYPE_MAP: dict[str, str] = {
    "guest": "VIRTUAL",
    "hypervisor": "SERVER",
    "mobile": "MOBILE",
}


def pick_hostname(*candidates: str | None) -> tuple[str, str | None]:
    """Return the ``(hostname, domain)`` of the first candidate the asset management API accepts."""
    for candidate in candidates:
        hostname, domain = split_hostname(candidate)
        if hostname:
            return hostname, domain
    # The platform cannot store a device without hostname yet (SekoiaLab/platform#98032)
    raise ValueError("no usable hostname")


class DeviceMapper:
    """The device of an InsightVM asset: only its essential fields."""

    def __init__(self, asset: Rapid7Asset) -> None:
        self.asset = asset

    def map(self) -> Device:
        """Raise ``ValueError`` when the asset has no usable host name: never the IP address or the id."""
        hostname, domain = pick_hostname(self.asset.host_name)
        device_type, device_type_id = self.map_device_type()
        return Device(
            uid=self.asset.id,
            hostname=hostname,
            domain=domain,
            ip=self.asset.ip or None,
            type=device_type,
            type_id=device_type_id,
        )

    def map_device_type(self) -> tuple[DeviceTypeStr, DeviceTypeId]:
        asset_type = ASSET_TYPE_MAP.get((self.asset.type or "").strip().lower())

        if asset_type is None:
            return DeviceTypeStr.UNKNOWN, DeviceTypeId.UNKNOWN
        return DeviceTypeStr[asset_type], DeviceTypeId[asset_type]
