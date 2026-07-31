from collections.abc import Generator
from datetime import datetime
from functools import cached_property

from dateutil.parser import isoparse
from pydantic import ValidationError
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
from sekoia_automation.asset_connector.models.ocsf.risk_level import RiskLevelId, RiskLevelStr
from sekoia_automation.storage import PersistentJSON

from holm_security.asset_connector.models import HolmDevice, HolmDevicePage
from holm_security.client import ApiClient


class HolmSecurityDeviceAssetConnector(AssetConnector):
    """Collect agent-managed devices from Holm Security and map them to OCSF."""

    # API configuration
    DEVICES_ENDPOINT: str = "/v2/devices"
    DEFAULT_PAGE_SIZE: int = 100
    REQUEST_TIMEOUT: int = 60

    # Product / metadata constants
    PRODUCT_NAME: str = "Holm Security"
    PRODUCT_VERSION: str = "v2"
    METADATA_VERSION: str = "1.5.0"

    # OCSF Device Inventory Info constants
    ACTIVITY_ID: int = 2
    ACTIVITY_NAME: str = "Collect"
    CATEGORY_NAME: str = "Discovery"
    CATEGORY_UID: int = 5
    CLASS_NAME: str = "Device Inventory Info"
    CLASS_UID: int = 5001
    TYPE_NAME: str = "Device Inventory Info: Collect"
    TYPE_UID: int = 500102

    # Holm max_severity -> OCSF risk level mapping
    MAX_SEVERITY_MAP: dict[str, tuple[RiskLevelStr, RiskLevelId]] = {
        "info": (RiskLevelStr.INFO, RiskLevelId.INFO),
        "low": (RiskLevelStr.LOW, RiskLevelId.LOW),
        "medium": (RiskLevelStr.MEDIUM, RiskLevelId.MEDIUM),
        "high": (RiskLevelStr.HIGH, RiskLevelId.HIGH),
        "critical": (RiskLevelStr.CRITICAL, RiskLevelId.CRITICAL),
    }

    # Holm os_family -> OCSF OS type mapping
    OS_FAMILY_MAP: dict[str, tuple[OSTypeStr, OSTypeId]] = {
        "windows": (OSTypeStr.WINDOWS, OSTypeId.WINDOWS),
        "linux": (OSTypeStr.LINUX, OSTypeId.LINUX),
        "macos": (OSTypeStr.MACOS, OSTypeId.MACOS),
        "mac": (OSTypeStr.MACOS, OSTypeId.MACOS),
        "android": (OSTypeStr.ANDROID, OSTypeId.ANDROID),
        "ios": (OSTypeStr.IOS, OSTypeId.IOS),
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("device_context.json", self._data_path)
        self._new_device_ids: set[str] = set()

    @property
    def most_recent_last_sync(self) -> str | None:
        with self.context as cache:
            return cache.get("most_recent_last_sync")

    @property
    def seen_device_ids(self) -> set[str]:
        with self.context as cache:
            return set(cache.get("seen_device_ids", []))


    @cached_property
    def base_url(self) -> str:
        return str(self.module.configuration["base_url"]).rstrip("/")

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(base_url=self.base_url, token=self.module.configuration["api_token"])

    @cached_property
    def metadata(self) -> Metadata:
        return Metadata(
            product=Product(name=self.PRODUCT_NAME, version=self.PRODUCT_VERSION),
            version=self.METADATA_VERSION,
        )

    @staticmethod
    def _to_epoch(value: str | None) -> float | None:
        """Convert an ISO 8601 timestamp to a Unix epoch float."""
        if not value:
            return None
        return isoparse(value).timestamp()

    @staticmethod
    def build_device_type(os_is_server: bool | None) -> tuple[DeviceTypeStr, DeviceTypeId]:
        """Map ``os_is_server`` to an OCSF device type."""
        if os_is_server:
            return DeviceTypeStr.SERVER, DeviceTypeId.SERVER

        if os_is_server is False:
            return DeviceTypeStr.DESKTOP, DeviceTypeId.DESKTOP

        return DeviceTypeStr.UNKNOWN, DeviceTypeId.UNKNOWN

    def build_operating_system(self, device: HolmDevice) -> OperatingSystem | None:
        """Map the Holm OS fields to an OCSF ``OperatingSystem`` object."""
        if device.os_name is None and device.os_family is None:
            return None

        os_type: OSTypeStr = OSTypeStr.UNKNOWN
        os_type_id: OSTypeId = OSTypeId.UNKNOWN
        if device.os_family:
            os_type, os_type_id = self.OS_FAMILY_MAP.get(
                device.os_family.strip().lower(), (OSTypeStr.OTHER, OSTypeId.OTHER)
            )

        return OperatingSystem(name=device.os_name, type=os_type, type_id=os_type_id)

    def build_network_interfaces(self, device: HolmDevice) -> list[NetworkInterface] | None:
        """Build the primary IPv4 and secondary IPv6 network interfaces."""
        network = device.network
        if network is None:
            return None

        interfaces: list[NetworkInterface] = []

        if network.ip_address:
            interfaces.append(
                NetworkInterface(
                    ip=network.ip_address,
                    mac=network.mac_address,
                    hostname=device.hostname,
                    type=NetworkInterfaceTypeStr.WIRED,
                    type_id=NetworkInterfaceTypeId.WIRED,
                )
            )

        if network.ip_address_v6:
            interfaces.append(
                NetworkInterface(
                    ip=network.ip_address_v6,
                    type=NetworkInterfaceTypeStr.WIRED,
                    type_id=NetworkInterfaceTypeId.WIRED,
                )
            )

        return interfaces or None

    def build_device(self, device: HolmDevice) -> Device:
        """Map a Holm device record to an OCSF ``Device`` object."""
        device_type, device_type_id = self.build_device_type(device.os_is_server)
        network = device.network

        risk_level, risk_level_id = self.MAX_SEVERITY_MAP.get(
            (device.max_severity or "").lower(), (None, None)
        ) if device.max_severity else (None, None)

        return Device(
            type=device_type,
            type_id=device_type_id,
            uid=device.uid,
            name=device.device_name,
            hostname=device.hostname or "",
            os=self.build_operating_system(device),
            ip=network.ip_address if network else None,
            network_interfaces=self.build_network_interfaces(device),
            created_time=self._to_epoch(device.created),
            last_seen_time=self._to_epoch(device.last_sync),
            is_managed=True,
            risk_score=device.risk_score if device.risk_score else None,
            risk_level=risk_level,
            risk_level_id=risk_level_id,
        )

    def map_fields(self, device: HolmDevice) -> DeviceOCSFModel:
        """Map a Holm device record to the OCSF Device Inventory Info model."""
        event_time = self._to_epoch(device.last_sync) or self._to_epoch(device.created)
        if event_time is None:
            raise ValueError(f"Device {device.uid} has neither last_sync nor created timestamp")

        return DeviceOCSFModel(
            activity_id=self.ACTIVITY_ID,
            activity_name=self.ACTIVITY_NAME,
            category_name=self.CATEGORY_NAME,
            category_uid=self.CATEGORY_UID,
            class_name=self.CLASS_NAME,
            class_uid=self.CLASS_UID,
            type_name=self.TYPE_NAME,
            type_uid=self.TYPE_UID,
            time=event_time,
            metadata=self.metadata,
            device=self.build_device(device),
        )

    def _fetch_device_pages(self, last_sync_from: str | None = None) -> Generator[HolmDevicePage, None, None]:
        """Fetch device pages, following the ``next`` URL until it is null."""
        url: str | None = f"{self.base_url}{self.DEVICES_ENDPOINT}"
        params: dict[str, int | str] = {"page_size": self.DEFAULT_PAGE_SIZE}
        if last_sync_from:
            params["last_sync_from"] = last_sync_from

        try:
            while url and self.running:
                response = self.client.get(url, params=params, timeout=self.REQUEST_TIMEOUT)
                response.raise_for_status()

                page = HolmDevicePage.model_validate(response.json())
                self.log(
                    message=f"Fetched {len(page.results)} devices (total {page.count})",
                    level="info",
                )

                yield page

                url = page.next
                # The `next` URL already carries the pagination query parameters.
                params = None
        except RequestException as error:
            self.log(message=f"Holm Security API request failed: {error}", level="error")
            raise

    def get_assets(self) -> Generator[DeviceOCSFModel, None, None]:
        """Yield OCSF device assets, skipping devices already seen via checkpoint."""
        checkpoint = self.most_recent_last_sync
        checkpoint_dt: datetime | None = isoparse(checkpoint) if checkpoint else None

        max_last_sync_dt: datetime | None = checkpoint_dt
        max_last_sync_raw: str | None = checkpoint

        generated = 0
        skipped = 0
        cached_ids = self.seen_device_ids

        for page in self._fetch_device_pages(last_sync_from=checkpoint_dt.date().isoformat() if checkpoint_dt else None):
            for device in page.results:
                device_dt = isoparse(device.last_sync) if device.last_sync else None

                # Deduplicate: skip devices already pushed in a previous run.
                if device.uid in cached_ids:
                    skipped += 1
                    continue

                # Client-side checkpoint filter: skip devices not modified since last run.
                if checkpoint_dt is not None and device_dt is not None and device_dt <= checkpoint_dt:
                    skipped += 1
                    continue

                if device_dt is not None and (max_last_sync_dt is None or device_dt > max_last_sync_dt):
                    max_last_sync_dt = device_dt
                    max_last_sync_raw = device.last_sync

                try:
                    asset = self.map_fields(device)
                except (ValueError, ValidationError) as error:
                    skipped += 1
                    self.log(message=f"Skipping device {device.uid}: {error}", level="warning")
                    continue

                self._new_device_ids.add(device.uid)
                generated += 1
                yield asset

        # Persist the new checkpoint only after the full run has been consumed.
        if max_last_sync_raw and max_last_sync_raw != checkpoint:
            self._latest_time = max_last_sync_raw

        self.log(
            message=f"Asset generation complete - generated: {generated}, skipped: {skipped}",
            level="info",
        )

    def update_checkpoint(self) -> None:
        if self._new_device_ids or self._latest_time:
            with self.context as cache:
                if self._latest_time:
                    cache["most_recent_last_sync"] = self._latest_time
                existing_ids: set[str] = set(cache.get("seen_device_ids", []))
                existing_ids.update(self._new_device_ids)
                cache["seen_device_ids"] = list(existing_ids)
            self._new_device_ids = set()
            self.log(
                message=f"Checkpoint updated - last_sync={self._latest_time}, "
                f"total cached IDs={len(existing_ids)}",
                level="debug",
            )
        else:
            self.log(message="No checkpoint update needed", level="debug")
