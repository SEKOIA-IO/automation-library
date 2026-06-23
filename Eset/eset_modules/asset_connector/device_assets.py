from collections.abc import Generator
from datetime import datetime, timedelta
from functools import cached_property
from typing import Optional
from urllib.parse import urljoin

from dateutil.parser import isoparse
from pydantic.v1 import ValidationError
from requests.exceptions import RequestException
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.group import Group
from sekoia_automation.asset_connector.models.ocsf.device import (
    Device,
    DeviceOCSFModel,
    DeviceTypeId,
    DeviceTypeStr,
    NetworkInterface,
    NetworkInterfaceTypeId,
    NetworkInterfaceTypeStr,
    OperatingSystem,
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.storage import PersistentJSON

from eset_modules.asset_connector.models import (
    EsetDevice,
    EsetDeviceGroup,
    EsetDeviceGroupPage,
    EsetDevicePage,
)
from eset_modules.client import ApiClient


class EsetDeviceAssetConnector(AssetConnector):

    # Endpoint constants
    DEVICES_ENDPOINT: str = "/v1/devices"
    DEVICE_GROUPS_ENDPOINT: str = "/v1/device_groups"
    DEFAULT_PAGE_SIZE: int = 100

    # Product constants
    PRODUCT_NAME: str = "ESET EDR"
    PRODUCT_VERSION: str = "9.1.2500.0"
    METADATA_VERSION: str = "1.5.0"

    # OCSF constants
    ACTIVITY_ID: int = 2
    ACTIVITY_NAME: str = "Collect"
    CATEGORY_NAME: str = "Discovery"
    CATEGORY_UID: int = 5
    CLASS_NAME: str = "Device Inventory Info"
    CLASS_UID: int = 5001
    TYPE_NAME: str = "Device Inventory Info: Collect"
    TYPE_UID: int = 500102

    OS_FAMILY_MAP: dict[int, tuple[OSTypeStr, OSTypeId]] = {
        1: (OSTypeStr.WINDOWS, OSTypeId.WINDOWS),
        2: (OSTypeStr.MACOS, OSTypeId.MACOS),
        3: (OSTypeStr.LINUX, OSTypeId.LINUX),
        4: (OSTypeStr.ANDROID, OSTypeId.ANDROID),
        5: (OSTypeStr.IOS, OSTypeId.IOS),
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("eset_device_context.json", self._data_path)
        self._latest_time: Optional[str] = None

    @property
    def most_recent_date_seen(self) -> Optional[str]:
        with self.context as cache:
            return cache.get("most_recent_date_seen")

    @cached_property
    def base_url(self) -> str:
        region = self.module.configuration.region
        return f"https://{region}.device-management.eset.systems"

    @cached_property
    def client(self) -> ApiClient:
        region = self.module.configuration.region
        return ApiClient(
            auth_base_url=f"https://{region}.business-account.iam.eset.systems",
            username=self.module.configuration.username,
            password=self.module.configuration.password,
        )

    @cached_property
    def metadata(self) -> Metadata:
        return Metadata(
            product=Product(name=self.PRODUCT_NAME, version=self.PRODUCT_VERSION),
            version=self.METADATA_VERSION,
        )

    @staticmethod
    def extract_timestamp(device: EsetDevice) -> Optional[datetime]:
        """Extract datetime from lastSyncTime field."""
        if device.lastSyncTime:
            try:
                return isoparse(device.lastSyncTime)
            except (ValueError, TypeError):
                pass
        return None

    def _resolve_os_type(self, family_id: Optional[int]) -> tuple[OSTypeStr, OSTypeId]:
        """Map ESET OS familyId to OCSF OS type."""
        if family_id is None:
            return OSTypeStr.UNKNOWN, OSTypeId.UNKNOWN
        return self.OS_FAMILY_MAP.get(family_id, (OSTypeStr.OTHER, OSTypeId.OTHER))

    def build_operating_system(self, device: EsetDevice) -> Optional[OperatingSystem]:
        """Build OCSF OperatingSystem from ESET device data."""
        os_data = device.operatingSystem
        if not os_data:
            return None

        os_type_str, os_type_id = self._resolve_os_type(os_data.familyId)
        name = os_data.displayName or (os_data.version.name if os_data.version else None)

        return OperatingSystem(
            name=name,
            type=os_type_str,
            type_id=os_type_id,
        )

    @staticmethod
    def _resolve_interface_type(caption: Optional[str]) -> tuple[NetworkInterfaceTypeStr, NetworkInterfaceTypeId]:
        """Guess the network interface type from its caption/name."""
        if caption:
            caption_upper = caption.upper()
            if any(kw in caption_upper for kw in ("WI-FI", "WIFI", "WIRELESS", "WLAN")):
                return NetworkInterfaceTypeStr.WIRELESS, NetworkInterfaceTypeId.WIRELESS
            if any(kw in caption_upper for kw in ("ETHERNET", "LAN", "WIRED", "REALTEK", "INTEL")):
                return NetworkInterfaceTypeStr.WIRED, NetworkInterfaceTypeId.WIRED
        return NetworkInterfaceTypeStr.UNKNOWN, NetworkInterfaceTypeId.UNKNOWN

    @staticmethod
    def _resolve_hostname(device: EsetDevice) -> str:
        """Resolve device hostname with fallback chain: displayName → originalDisplayName → uuid."""
        return device.displayName or device.originalDisplayName or device.uuid

    def build_network_interfaces(self, device: EsetDevice) -> Optional[list[NetworkInterface]]:
        """Build OCSF NetworkInterface list from hardware profile network adapters."""
        interfaces: list[NetworkInterface] = []
        resolved_hostname = self._resolve_hostname(device)

        if device.primaryLocalIpAddress:
            interfaces.append(
                NetworkInterface(
                    ip=device.primaryLocalIpAddress,
                    type=NetworkInterfaceTypeStr.UNKNOWN,
                    type_id=NetworkInterfaceTypeId.UNKNOWN,
                    hostname=resolved_hostname,
                )
            )

        # Extract MAC addresses from hardware profiles and enrich existing interfaces
        if device.hardwareProfiles:
            for profile in device.hardwareProfiles:
                if profile.networkAdapters:
                    for adapter in profile.networkAdapters:
                        if adapter.macAddress:
                            type_str, type_id = self._resolve_interface_type(adapter.caption)
                            # Search for an existing interface without a MAC to enrich
                            unmatched = next((iface for iface in interfaces if not iface.mac), None)
                            if unmatched:
                                unmatched.mac = adapter.macAddress
                                unmatched.name = adapter.caption
                                unmatched.type = type_str
                                unmatched.type_id = type_id
                            else:
                                interfaces.append(
                                    NetworkInterface(
                                        mac=adapter.macAddress,
                                        name=adapter.caption,
                                        type=type_str,
                                        type_id=type_id,
                                    )
                                )

        # Add public IP as a separate network interface if present and different from local IP
        if device.publicIpAddress and device.publicIpAddress != device.primaryLocalIpAddress:
            interfaces.append(
                NetworkInterface(
                    ip=device.publicIpAddress,
                    type=NetworkInterfaceTypeStr.UNKNOWN,
                    type_id=NetworkInterfaceTypeId.UNKNOWN,
                )
            )

        return interfaces if interfaces else None

    def _resolve_device_type(self, device: EsetDevice) -> tuple[DeviceTypeStr, DeviceTypeId]:
        """Resolve OCSF device type from ESET deviceType and isMobile flag."""
        if device.isMobile:
            return DeviceTypeStr.MOBILE, DeviceTypeId.MOBILE

        device_type = (device.deviceType or "").upper()
        if "SERVER" in device_type:
            return DeviceTypeStr.SERVER, DeviceTypeId.SERVER
        if "VIRTUAL" in device_type:
            return DeviceTypeStr.VIRTUAL, DeviceTypeId.VIRTUAL

        return DeviceTypeStr.DESKTOP, DeviceTypeId.DESKTOP

    def build_device(self, eset_device: EsetDevice, groups: list[EsetDeviceGroup]) -> Device:
        """Build OCSF Device from ESET device and group data."""

        last_seen_time = None
        ts = self.extract_timestamp(eset_device)
        if ts:
            last_seen_time = ts.timestamp()

        hostname = self._resolve_hostname(eset_device)
        device_type_str, device_type_id = self._resolve_device_type(eset_device)
        network_interfaces = self.build_network_interfaces(eset_device)
        os = self.build_operating_system(eset_device)

        ocsf_groups = None
        if groups:
            ocsf_groups = [Group(name=g.displayName or g.uuid, uid=g.uuid) for g in groups]

        model = None
        manufacturer = None
        if eset_device.hardwareProfiles:
            model = eset_device.hardwareProfiles[0].model
            manufacturer = eset_device.hardwareProfiles[0].manufacturer

        return Device(
            uid=eset_device.uuid,
            hostname=hostname,
            name=eset_device.displayName,
            type=device_type_str,
            type_id=device_type_id,
            os=os,
            ip=eset_device.primaryLocalIpAddress,
            network_interfaces=network_interfaces,
            last_seen_time=last_seen_time,
            desc=eset_device.description,
            is_managed=True,
            model=model,
            vendor_name=manufacturer,
            domain=eset_device.managementDomain,
            groups=ocsf_groups,
        )

    def map_fields(self, eset_device: EsetDevice, groups: list[EsetDeviceGroup]) -> DeviceOCSFModel:
        """Map ESET device and group data to a full OCSF DeviceOCSFModel."""
        self.log(f"Mapping device - UUID: {eset_device.uuid}, Name: {eset_device.displayName}", level="debug")

        ts = self.extract_timestamp(eset_device)
        time = ts.timestamp() if ts else datetime.utcnow().timestamp()

        return DeviceOCSFModel(
            activity_id=self.ACTIVITY_ID,
            activity_name=self.ACTIVITY_NAME,
            category_name=self.CATEGORY_NAME,
            category_uid=self.CATEGORY_UID,
            class_name=self.CLASS_NAME,
            class_uid=self.CLASS_UID,
            type_name=self.TYPE_NAME,
            type_uid=self.TYPE_UID,
            time=time,
            metadata=self.metadata,
            device=self.build_device(eset_device, groups),
        )

    def _fetch_all_groups(self) -> dict[str, EsetDeviceGroup]:
        """Fetch all device groups and return as a dict keyed by uuid."""
        groups: dict[str, EsetDeviceGroup] = {}
        url = urljoin(self.base_url, self.DEVICE_GROUPS_ENDPOINT)
        params: dict[str, str | int] = {"pageSize": self.DEFAULT_PAGE_SIZE}

        self.log("Fetching all device groups", level="info")

        try:
            while self.running:
                response = self.client.get(url, params=params, timeout=60)
                response.raise_for_status()
                raw = response.json()

                try:
                    page = EsetDeviceGroupPage.parse_obj(raw)
                except ValidationError as e:
                    self.log(f"Failed to parse device groups page: {e}", level="warning")
                    break

                for group in page.deviceGroups:
                    groups[group.uuid] = group

                if not page.nextPageToken:
                    break
                params = {"pageSize": self.DEFAULT_PAGE_SIZE, "pageToken": page.nextPageToken}

        except RequestException as e:
            self.log(f"Failed to fetch device groups: {e}", level="warning")

        self.log(f"Fetched {len(groups)} device groups", level="info")
        return groups

    def _fetch_devices(self) -> Generator[list[EsetDevice], None, None]:
        """Fetch all devices with pagination."""
        url = urljoin(self.base_url, self.DEVICES_ENDPOINT)
        params: dict[str, str | int] = {"pageSize": self.DEFAULT_PAGE_SIZE}

        self.log("Fetching ESET devices", level="info")

        try:
            page_number = 1
            while self.running:
                response = self.client.get(url, params=params, timeout=60)
                response.raise_for_status()
                raw = response.json()

                try:
                    page = EsetDevicePage.parse_obj(raw)
                except ValidationError as e:
                    self.log(f"Failed to parse devices page {page_number}: {e}", level="warning")
                    break

                self.log(f"Retrieved page {page_number} - {len(page.devices)} devices", level="info")

                if not page.devices:
                    break

                # Devices are already validated by pydantic when building `EsetDevicePage`.
                yield page.devices

                if not page.nextPageToken:
                    self.log(f"Pagination complete after {page_number} pages", level="info")
                    break

                params = {"pageSize": self.DEFAULT_PAGE_SIZE, "pageToken": page.nextPageToken}
                page_number += 1

        except RequestException as e:
            self.log(f"API request failed while fetching devices: {e}", level="error")
            raise

    def iterate_devices(self) -> Generator[list[EsetDevice], None, None]:
        """
        Iterate over ESET devices, filtering out already-seen devices via lastSyncTime checkpoint.
        """
        max_date: Optional[datetime] = isoparse(self._latest_time) if self._latest_time else None
        checkpoint_date = isoparse(self.most_recent_date_seen) if self.most_recent_date_seen else None
        total_fetched = 0
        total_skipped = 0
        total_yielded = 0

        self.log(f"Starting device iteration - Checkpoint: {self.most_recent_date_seen or 'None'}", level="info")

        try:
            for devices in self._fetch_devices():
                if not devices:
                    continue

                total_fetched += len(devices)
                new_devices: list[EsetDevice] = []

                for device in devices:
                    ts = self.extract_timestamp(device)

                    if ts:
                        candidate = ts + timedelta(microseconds=1)
                        if max_date is None or candidate > max_date:
                            max_date = candidate

                        if checkpoint_date and ts <= checkpoint_date:
                            total_skipped += 1
                            continue

                    new_devices.append(device)
                    total_yielded += 1

                if new_devices:
                    yield new_devices

            self.log(
                f"Device iteration complete - Fetched: {total_fetched}, "
                f"New/updated: {total_yielded}, Skipped (already seen): {total_skipped}",
                level="info",
            )

            if max_date and (checkpoint_date is None or max_date > checkpoint_date):
                self._latest_time = max_date.isoformat()

        except Exception as e:
            self.log(f"Device iteration failed: {e}", level="error")
            raise

    def update_checkpoint(self) -> None:
        """Persist the latest timestamp seen to the context file."""
        if self._latest_time:
            with self.context as cache:
                cache["most_recent_date_seen"] = self._latest_time
            self.log(f"Checkpoint updated to: {self._latest_time}", level="debug")
        else:
            self.log("No checkpoint update needed", level="debug")

    def get_assets(self) -> Generator[DeviceOCSFModel, None, None]:
        """Main entry point. Fetch all ESET devices and yield OCSF DeviceOCSFModel instances."""
        self.log("Starting ESET device asset collection", level="info")

        all_groups = self._fetch_all_groups()

        assets_generated = 0
        assets_skipped = 0

        try:
            for devices in self.iterate_devices():
                for device in devices:
                    try:
                        device_groups: list[EsetDeviceGroup] = []
                        if device.parentGroupUuid and device.parentGroupUuid in all_groups:
                            device_groups.append(all_groups[device.parentGroupUuid])

                        yield self.map_fields(device, device_groups)
                        assets_generated += 1
                    except (KeyError, ValueError) as e:
                        assets_skipped += 1
                        self.log(
                            f"Asset skipped - UUID: {device.uuid}, Reason: {e}",
                            level="warning",
                        )
                        continue

            self.log(
                f"Asset collection complete - Generated: {assets_generated}, Skipped: {assets_skipped}",
                level="info",
            )

        except Exception as e:
            self.log(
                f"Asset collection failed - Generated: {assets_generated}, Skipped: {assets_skipped}, Error: {e}",
                level="error",
            )
            raise
