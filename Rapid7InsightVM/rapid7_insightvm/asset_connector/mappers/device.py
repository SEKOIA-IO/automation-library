from sekoia_automation.asset_connector.models.ocsf.device import Device, DeviceTypeId, DeviceTypeStr

from rapid7_insightvm.asset_connector.models import Rapid7Asset

ASSET_TYPE_MAP: dict[str, str] = {
    "guest": "VIRTUAL",
    "hypervisor": "SERVER",
    "mobile": "MOBILE",
}


class DeviceMapper:
    """The device of an InsightVM asset: only its essential fields."""

    def __init__(self, asset: Rapid7Asset) -> None:
        self.asset = asset

    def map(self) -> Device:
        device_type, device_type_id = self.map_device_type()
        return Device(
            uid=self.asset.id,
            hostname=self.hostname,
            type=device_type,
            type_id=device_type_id,
        )

    @property
    def hostname(self) -> str:
        return self.asset.host_name or self.asset.ip or self.asset.id

    def map_device_type(self) -> tuple[DeviceTypeStr, DeviceTypeId]:
        asset_type = ASSET_TYPE_MAP.get((self.asset.type or "").strip().lower())

        if asset_type is None:
            return DeviceTypeStr.UNKNOWN, DeviceTypeId.UNKNOWN
        return DeviceTypeStr[asset_type], DeviceTypeId[asset_type]
