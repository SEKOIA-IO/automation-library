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
    NetworkInterface,
    GeoLocation,
)
from sekoia_automation.asset_connector.models.ocsf.group import Group
from sekoia_automation.asset_connector.models.ocsf.organization import Organization
from sekoia_automation.storage import PersistentJSON

from crowdstrike_falcon.client import CrowdstrikeFalconClient


class CrowdstrikeDeviceAssetConnector(AssetConnector):
    PRODUCT_NAME: str = "Crowdstrike Falcon"
    PRODUCT_VERSION: str = "N/A"
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

    @staticmethod
    def parse_timestamp(ts: str | None) -> float | None:
        """
        Parse an ISO 8601 timestamp string and return a UNIX timestamp (float).
        """
        if not ts:
            return None
        try:
            return isoparse(ts).timestamp()
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def normalize_mac_address(mac: str | None) -> str | None:
        """
        Normalize MAC address to standard format (e.g., "00:1A:2B:3C:4D:5E").
        """
        if not mac:
            return None
        return mac.replace("-", ":").upper()

    def get_device_os(self, device: dict[str, Any]) -> OperatingSystem:
        """
        Determine the operating system from device data.
        Maps platform_name to OCSF OS type and includes version info.
        """
        platform_name = device.get("platform_name")
        os_version = device.get("os_version")
        kernel_version = device.get("kernel_version")

        if not platform_name:
            return OperatingSystem(
                name=os_version or "Unknown",
                type=OSTypeStr.UNKNOWN,
                type_id=OSTypeId.UNKNOWN,
            )

        platform_lower = platform_name.lower()

        os_mapping: dict[str, tuple[OSTypeId, OSTypeStr, str]] = {
            "windows": (OSTypeId.WINDOWS, OSTypeStr.WINDOWS, "Windows"),
            "linux": (OSTypeId.LINUX, OSTypeStr.LINUX, "Linux"),
            "mac": (OSTypeId.MACOS, OSTypeStr.MACOS, "macOS"),
            "macos": (OSTypeId.MACOS, OSTypeStr.MACOS, "macOS"),
            "ios": (OSTypeId.IOS, OSTypeStr.IOS, "iOS"),
            "android": (OSTypeId.ANDROID, OSTypeStr.ANDROID, "Android"),
        }

        for key, (type_id, type_str, name) in os_mapping.items():
            if key in platform_lower:
                display_name = os_version if os_version else name
                return OperatingSystem(
                    name=display_name,
                    type=type_str,
                    type_id=type_id,
                )

        return OperatingSystem(
            name=os_version or platform_name,
            type=OSTypeStr.UNKNOWN,
            type_id=OSTypeId.UNKNOWN,
        )

    def get_device_type(self, device: dict[str, Any]) -> tuple[DeviceTypeId, DeviceTypeStr]:
        """
        Determine the device type from product_type_desc.
        Maps CrowdStrike product types to OCSF device types.
        """
        product_type_desc = device.get("product_type_desc", "")
        device_type = product_type_desc.lower() if product_type_desc else ""

        type_mapping: dict[str, tuple[DeviceTypeId, DeviceTypeStr]] = {
            "server": (DeviceTypeId.SERVER, DeviceTypeStr.SERVER),
            "workstation": (DeviceTypeId.DESKTOP, DeviceTypeStr.DESKTOP),
            "desktop": (DeviceTypeId.DESKTOP, DeviceTypeStr.DESKTOP),
            "laptop": (DeviceTypeId.LAPTOP, DeviceTypeStr.LAPTOP),
            "mobile": (DeviceTypeId.MOBILE, DeviceTypeStr.MOBILE),
            "tablet": (DeviceTypeId.TABLET, DeviceTypeStr.TABLET),
            "phone": (DeviceTypeId.MOBILE, DeviceTypeStr.MOBILE),
            "virtual": (DeviceTypeId.VIRTUAL, DeviceTypeStr.VIRTUAL),
        }

        for key, (type_id, type_str) in type_mapping.items():
            if key in device_type:
                return type_id, type_str

        return DeviceTypeId.UNKNOWN, DeviceTypeStr.UNKNOWN

    def get_firewall_status(self, device: dict[str, Any]) -> Literal["Disabled", "Enabled"]:
        """
        Determine firewall status from device policies.
        """
        firewall_policy = device.get("device_policies", {}).get("firewall", {})
        if firewall_policy.get("applied"):
            return "Enabled"
        return "Disabled"

    def get_network_interfaces(self, device: dict[str, Any]) -> list[NetworkInterface] | None:
        """
        Extract network interfaces from device data.
        Creates interfaces for local IP, external IP, and connection IP.
        """
        interfaces: list[NetworkInterface] = []

        local_ip = device.get("local_ip")
        mac_address = device.get("mac_address")
        hostname = device.get("hostname")

        if local_ip or mac_address:
            interfaces.append(
                NetworkInterface(
                    hostname=hostname,
                    ip=local_ip,
                    mac=self.normalize_mac_address(mac_address),
                    name="primary",
                )
            )

        connection_ip = device.get("connection_ip")
        connection_mac = device.get("connection_mac_address")

        if connection_ip and connection_ip != local_ip:
            interfaces.append(
                NetworkInterface(
                    ip=connection_ip,
                    mac=self.normalize_mac_address(connection_mac),
                    name="connection",
                )
            )

        return interfaces if interfaces else None

    def get_groups(self, device: dict[str, Any]) -> list[Group] | None:
        """
        Extract groups from device data.
        """
        raw_groups = device.get("groups", [])
        if not raw_groups:
            return None

        groups = [Group(uid=g) for g in raw_groups if g]
        return groups if groups else None

    def get_location(self, device: dict[str, Any]) -> GeoLocation | None:
        """
        Extract geographic location from device data.
        Uses zone_group for region information.
        """
        zone_group = device.get("zone_group")
        if zone_group:
            return GeoLocation(country=zone_group[:2].upper() if len(zone_group) >= 2 else None)
        return None

    def get_organization(self, device: dict[str, Any]) -> Organization | None:
        """
        Extract organization info from device data.
        Uses CID and service provider account info.
        """
        cid = device.get("cid")
        account_id = device.get("service_provider_account_id")

        if cid or account_id:
            return Organization(
                uid=cid,
                name=device.get("service_provider"),
            )
        return None

    def is_device_compliant(self, device: dict[str, Any]) -> bool | None:
        """
        Determine if device is compliant based on policies and status.
        """
        status = device.get("status")
        rfm = device.get("reduced_functionality_mode")
        containment = device.get("filesystem_containment_status")

        # Device is compliant if status is normal, not in RFM, and not contained
        if status == "normal" and rfm == "no" and containment == "normal":
            return True
        elif status or rfm or containment:
            return False
        return None

    def get_enrichments(self, device: dict[str, Any]) -> list[DeviceEnrichmentObject]:
        """
        Create enrichment objects with additional CrowdStrike-specific data.
        """
        enrichments: list[DeviceEnrichmentObject] = []

        enrichments.append(
            DeviceEnrichmentObject(
                name="compliance",
                value="hygiene",
                data=DeviceDataObject(
                    Firewall_status=self.get_firewall_status(device),
                ),
            )
        )

        return enrichments

    def map_device_fields(self, device: dict[str, Any]) -> DeviceOCSFModel:
        """
        Map Crowdstrike device fields to OCSF device model.
        Extracts maximum fields from CrowdStrike API response.
        """
        # Metadata
        product = Product(name=self.PRODUCT_NAME, version=self.PRODUCT_VERSION)
        metadata = Metadata(product=product, version=self.OCSF_VERSION)

        # Device attributes
        device_os = self.get_device_os(device)
        type_id, type_str = self.get_device_type(device)

        # Timestamps
        first_seen = device.get("first_seen")
        last_seen = device.get("last_seen")
        modified_timestamp = device.get("modified_timestamp")
        agent_local_time = device.get("agent_local_time")

        # Create Device object with all available fields
        crowdstrike_device = Device(
            # Required fields
            uid=device.get("device_id", ""),
            hostname=device.get("hostname", ""),
            type_id=type_id,
            type=type_str,
            # Operating System
            os=device_os,
            # Network
            ip=device.get("external_ip"),
            network_interfaces=self.get_network_interfaces(device),
            subnet=device.get("default_gateway_ip"),
            # Identity
            uid_alt=device.get("serial_number"),
            domain=device.get("machine_domain") or None,
            name=device.get("hostname"),
            # Timestamps
            first_seen_time=self.parse_timestamp(first_seen),
            last_seen_time=self.parse_timestamp(last_seen),
            created_time=self.parse_timestamp(first_seen),
            boot_time=self.parse_timestamp(agent_local_time),
            # Hardware
            model=device.get("system_product_name"),
            vendor_name=device.get("system_manufacturer"),
            hypervisor=device.get("bios_manufacturer"),
            desc=device.get("product_type_desc"),
            # Cloud/Virtual
            region=device.get("zone_group"),
            # Organization
            org=self.get_organization(device),
            # Groups
            groups=self.get_groups(device),
            # Location
            location=self.get_location(device),
            # Compliance/Management
            is_managed=True,  # Managed by CrowdStrike
            is_compliant=self.is_device_compliant(device),
        )

        # Enrichments
        enrichments = self.get_enrichments(device)

        # Determine event time
        event_time = self.parse_timestamp(modified_timestamp) or self.parse_timestamp(first_seen)
        if event_time is None:
            event_time = datetime.now().timestamp()

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
            time=event_time,
            metadata=metadata,
            device=crowdstrike_device,
            enrichments=enrichments,
        )

        return device_ocsf

    def update_checkpoint(self) -> None:
        """Update the checkpoint with the latest device ID."""
        self.log("Updating the device id !!", level="info")
        if self._latest_id is None:
            return
        with self.context as cache:
            cache["most_recent_device_id"] = self._latest_id
            self.log(f"Device id was updated to {self._latest_id}", level="info")

    def next_devices(self) -> Generator[dict[str, Any], None, None]:
        """
        Generator that yields device information from CrowdStrike API.
        Uses pagination and checkpoint to fetch only new devices.
        """
        last_first_uuid = self.most_recent_device_id
        uuids_batch: list[str] = []

        for idx, device_uuid in enumerate(self.client.list_devices_uuids(limit=self.LIMIT, sort="first_seen.desc")):
            if idx == 0:
                if device_uuid == last_first_uuid:
                    self.log("No device has been added !!", level="info")
                    return
                self._latest_id = device_uuid

            # Stop before the last seen device id
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
        """
        Main generator that yields OCSF-formatted device assets.
        """
        self.log("Start the getting assets generator !!", level="info")
        for device in self.next_devices():
            yield self.map_device_fields(device)
