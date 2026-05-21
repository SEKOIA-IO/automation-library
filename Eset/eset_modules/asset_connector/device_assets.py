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
    PRODUCT_VERSION: str = "1.0"
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

    # OS family ID to OCSF OS type mapping (ESET uses numeric familyId for OS type)
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

    @property
    def most_recent_date_seen(self) -> Optional[str]:
        with self.context as cache:
            return cache.get("most_recent_date_seen")

    @cached_property
    def base_url(self) -> str:
        region = self.module.configuration.region
        return f"https://{region}.automation.eset.systems"

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

    def build_network_interfaces(self, device: EsetDevice) -> Optional[list[NetworkInterface]]:
        """Build OCSF NetworkInterface list from hardware profile network adapters."""
        interfaces: list[NetworkInterface] = []

        if device.primaryLocalIpAddress:
            interfaces.append(
                NetworkInterface(
                    ip=device.primaryLocalIpAddress,
                    type=NetworkInterfaceTypeStr.WIRED,
                    type_id=NetworkInterfaceTypeId.WIRED,
                    hostname=device.displayName,
                )
            )

        # Extract MAC addresses from hardware profiles
        if device.hardwareProfiles:
            for profile in device.hardwareProfiles:
                if profile.networkAdapters:
                    for adapter in profile.networkAdapters:
                        if adapter.macAddress:
                            # Check if we already have an interface with same IP to enrich it
                            if interfaces and not interfaces[0].mac:
                                interfaces[0].mac = adapter.macAddress
                                interfaces[0].name = adapter.caption
                            else:
                                interfaces.append(
                                    NetworkInterface(
                                        mac=adapter.macAddress,
                                        name=adapter.caption,
                                        type=NetworkInterfaceTypeStr.WIRED,
                                        type_id=NetworkInterfaceTypeId.WIRED,
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
        from sekoia_automation.asset_connector.models.ocsf.group import Group

        last_seen_time = None
        ts = self.extract_timestamp(eset_device)
        if ts:
            last_seen_time = ts.timestamp()

        device_type_str, device_type_id = self._resolve_device_type(eset_device)
        network_interfaces = self.build_network_interfaces(eset_device)
        os = self.build_operating_system(eset_device)

        # Map device groups to OCSF Group objects
        ocsf_groups = None
        if groups:
            ocsf_groups = [Group(name=g.displayName or g.uuid, uid=g.uuid) for g in groups]

        # Get hardware model from first profile if available
        model = None
        if eset_device.hardwareProfiles:
            model = eset_device.hardwareProfiles[0].model

        hostname = eset_device.displayName or eset_device.originalDisplayName or eset_device.uuid

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
                response = self.client.get(url, params=params)
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
                response = self.client.get(url, params=params)
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

                valid_devices: list[EsetDevice] = []
                for item in page.devices:
                    try:
                        valid_devices.append(item)
                    except ValidationError as e:
                        self.log(f"Skipping invalid device: {e}", level="warning")

                if valid_devices:
                    yield valid_devices

                if not page.nextPageToken:
                    self.log(f"Pagination complete after {page_number} pages", level="info")
                    break

                params = {"pageSize": self.DEFAULT_PAGE_SIZE, "pageToken": page.nextPageToken}
                page_number += 1

        except RequestException as e:
            self.log(f"API request failed while fetching devices: {e}", level="error")
            raise

    def iterate_devices(self) -> Generator[list[EsetDevice], None, None]:
        """Iterate over all ESET devices, tracking the most recent sync time."""
        max_date: Optional[datetime] = None
        orig_date = isoparse(self.most_recent_date_seen) if self.most_recent_date_seen else None
        device_count = 0

        self.log(f"Starting device iteration - Checkpoint: {self.most_recent_date_seen or 'None'}", level="info")

        try:
            for devices in self._fetch_devices():
                if not devices:
                    continue

                device_count += len(devices)

                for device in devices:
                    ts = self.extract_timestamp(device)
                    if ts:
                        candidate = ts + timedelta(microseconds=1)
                        if max_date is None or candidate > max_date:
                            max_date = candidate

                yield devices

            self.log(f"Device iteration complete - {device_count} devices processed", level="info")

            if max_date and (orig_date is None or max_date > orig_date):
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

        # Pre-load all device groups to enrich devices with group membership
        all_groups = self._fetch_all_groups()

        assets_generated = 0
        assets_skipped = 0

        try:
            for devices in self.iterate_devices():
                for device in devices:
                    try:
                        # Resolve the device's parent group if available
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
