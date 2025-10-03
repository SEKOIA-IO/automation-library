from functools import cached_property
from collections.abc import Generator
from typing import Any, Literal
from datetime import datetime

from dateutil.parser import isoparse
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import (
    Metadata,
    Product,
)
from sekoia_automation.asset_connector.models.ocsf.device import (
    DeviceOCSFModel,
    OperatingSystem,
    OSTypeStr,
    OSTypeId,
    Device,
    DeviceTypeId,
    DeviceTypeStr,
    DeviceEnrichmentObject,
    DeviceDataObject,
)
from sekoia_automation.storage import PersistentJSON

from crowdstrike_falcon.client import CrowdstrikeFalconClient


class CrowdstrikeDeviceAssetConnector(AssetConnector):

    PRODUCT_NAME: str = "Crowdstrike Falcon"
    PRODUCT_VERSION = "N/A"
    OCSF_VERSION: str = "1.6.0"
    LIMIT: int = 100

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self._latest_id = None

    @property
    def most_recent_device_id(self) -> str | None:
        with self.context as cache:
            return cache.get("most_recent_device_id", None)

    @cached_property
    def _http_default_headers(self) -> dict[str, str]:
        return {
            "User-Agent": "sekoiaio-connector/{0}-{1}".format(
                self.module.manifest.get("slug"), self.module.manifest.get("version")
            ),
        }

    @cached_property
    def client(self) -> CrowdstrikeFalconClient:
        return CrowdstrikeFalconClient(
            self.module.configuration.base_url,
            self.module.configuration.client_id,
            self.module.configuration.client_secret,
            default_headers=self._http_default_headers,
        )

    def get_device_os(self, platform_details: str | None) -> OperatingSystem:
        """
        Determine the operating system from platform details string.
        """
        if not platform_details:
            return OperatingSystem(name="Unknown", type=OSTypeStr.UNKNOWN, type_id=OSTypeId.UNKNOWN)

        platform_lower = platform_details.lower()

        if "windows" in platform_lower:
            return OperatingSystem(name="Windows", type=OSTypeStr.WINDOWS, type_id=OSTypeId.WINDOWS)
        elif "linux" in platform_lower or "unix" in platform_lower:
            return OperatingSystem(name="Linux", type=OSTypeStr.LINUX, type_id=OSTypeId.LINUX)
        elif "macos" in platform_lower or "mac" in platform_lower:
            return OperatingSystem(name="MacOS", type=OSTypeStr.MACOS, type_id=OSTypeId.MACOS)
        else:
            return OperatingSystem(name=platform_details, type=OSTypeStr.UNKNOWN, type_id=OSTypeId.UNKNOWN)

    def get_device_type(self, device_type: str | None) -> tuple[DeviceTypeId, DeviceTypeStr]:
        """
        Determine the device type from device type description string.
        """
        device_type = device_type.lower() if device_type else ""
        if device_type in ["desktop", "laptop", "workstation"]:
            return DeviceTypeId.DESKTOP, DeviceTypeStr.DESKTOP
        elif device_type in ["server"]:
            return DeviceTypeId.SERVER, DeviceTypeStr.SERVER
        elif device_type in ["mobile", "tablet", "phone"]:
            return DeviceTypeId.MOBILE, DeviceTypeStr.MOBILE
        else:
            return DeviceTypeId.UNKNOWN, DeviceTypeStr.UNKNOWN

    def get_firewall_status(self, device: dict[str, Any]) -> Literal["Disabled", "Enabled"]:
        firewall_applied = device.get("device_policies", {}).get("Firewall", {}).get("applied")
        if firewall_applied:
            return "Enabled"
        return "Disabled"

    def map_device_fields(self, device: dict[str, Any]) -> DeviceOCSFModel:
        """
        Map Crowdstrike device fields to OCSF device model.
        """
        product = Product(name=self.PRODUCT_NAME, version=self.PRODUCT_VERSION)
        metadata = Metadata(product=product, version=self.OCSF_VERSION)
        device_os = self.get_device_os(device.get("platform_name"))
        type_id, type_str = self.get_device_type(device.get("product_type_desc"))
        first_seen: str = device.get("first_seen", "")
        enrichment_object = DeviceEnrichmentObject(
            name="compliance",
            value="hygiene",
            data=DeviceDataObject(
                Firewall_status=self.get_firewall_status(device),
            ),
        )
        crowdstrike_device = Device(
            uid=device.get("device_id"), hostname=device.get("hostname"), os=device_os, type_id=type_id, type=type_str
        )

        # Create OCSF device inventory event
        device_ocsf = DeviceOCSFModel(
            activity_id=2,
            activity_name="Collect",
            category_name="Discovery",
            category_uid=5,
            class_name="Device Inventory Info",
            class_uid=5001,
            type_name="Device Inventory Info: Collect",
            severity="Informational",
            severity_id=1,
            type_uid=500102,
            time=(isoparse(first_seen).timestamp() if first_seen else datetime.now().timestamp()),
            metadata=metadata,
            device=crowdstrike_device,
            enrichments=[enrichment_object],
        )

        return device_ocsf

    def update_checkpoint(self) -> None:
        self.log("Updating the device id !!", level="info")
        if self._latest_id is None:
            return
        with self.context as cache:
            cache["most_recent_device_id"] = self._latest_id
            self.log(f"Device id was updated to {self._latest_id}", level="info")

    def next_devices(self) -> Generator[dict[str, Any], None, None]:
        last_first_uuid = self.most_recent_device_id
        uuids_batch: list[str] = []

        for idx, device_uuid in enumerate(self.client.list_devices_uuids(limit=self.LIMIT, sort="first_seen.desc")):
            if idx == 0:
                if device_uuid == last_first_uuid:
                    self.log("No device has been added !!", level="info")
                    return
                self._latest_id = device_uuid

            # Stopping before the last seen user id
            if last_first_uuid and device_uuid == last_first_uuid:
                break

            uuids_batch.append(device_uuid)

            if len(uuids_batch) >= self.LIMIT:
                self.log(f"Found {len(uuids_batch)} devices !!", level="info")
                for device_info in self.client.get_devices_infos(uuids_batch):
                    yield device_info
                uuids_batch = []

        if uuids_batch:
            self.log(f"Found {len(uuids_batch)} devices in the last batch!!", level="info")
            for device_info in self.client.get_devices_infos(uuids_batch):
                yield device_info

    def get_assets(self) -> Generator[DeviceOCSFModel, None, None]:
        self.log("Start the getting assets generator !!", level="info")
        for device in self.next_devices():
            yield self.map_device_fields(device)
