from collections.abc import Generator
from datetime import datetime
from functools import cached_property

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
    OperatingSystem,
)
from sekoia_automation.asset_connector.models.ocsf.risk_level import RiskLevelId, RiskLevelStr
from sekoia_automation.storage import PersistentJSON

from holm_security.asset_connector import mappers
from holm_security.asset_connector.models import (
    HolmDevice,
    HolmDevicePage,
    HolmNetAsset,
    HolmNetAssetPage,
)
from holm_security.client import ApiClient


class HolmSecurityDeviceAssetConnector(AssetConnector):
    """Collect Holm Security assets and map them to OCSF.

    Two inventories are published under the same class: the agent-managed devices of
    ``GET /v2/devices`` and the scanned network assets of ``GET /v2/net-assets``.
    """

    # API configuration
    DEVICES_ENDPOINT: str = "/v2/devices"
    NET_ASSETS_ENDPOINT: str = "/v2/net-assets"
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

    # Holm max_severity -> OCSF risk level mapping. The devices endpoint reports the
    # severity as an integer, older payloads use the bucket name.
    MAX_SEVERITY_MAP: dict[str, tuple[RiskLevelStr, RiskLevelId]] = {
        "info": (RiskLevelStr.INFO, RiskLevelId.INFO),
        "low": (RiskLevelStr.LOW, RiskLevelId.LOW),
        "medium": (RiskLevelStr.MEDIUM, RiskLevelId.MEDIUM),
        "high": (RiskLevelStr.HIGH, RiskLevelId.HIGH),
        "critical": (RiskLevelStr.CRITICAL, RiskLevelId.CRITICAL),
        "0": (RiskLevelStr.INFO, RiskLevelId.INFO),
        "1": (RiskLevelStr.LOW, RiskLevelId.LOW),
        "2": (RiskLevelStr.MEDIUM, RiskLevelId.MEDIUM),
        "3": (RiskLevelStr.HIGH, RiskLevelId.HIGH),
        "4": (RiskLevelStr.CRITICAL, RiskLevelId.CRITICAL),
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("device_context.json", self._data_path)
        self._latest_time: str | None = None
        self._latest_net_asset_time: str | None = None
        self._new_device_ids: set[str] = set()
        self._generated: int = 0
        self._skipped: int = 0

    @property
    def most_recent_last_sync(self) -> str | None:
        with self.context as cache:
            return cache.get("most_recent_last_sync")

    @property
    def most_recent_net_asset_last_detected(self) -> str | None:
        with self.context as cache:
            return cache.get("most_recent_net_asset_last_detected")

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
        return mappers.to_epoch(value)

    @staticmethod
    def build_device_type(os_is_server: bool | None) -> tuple[DeviceTypeStr, DeviceTypeId]:
        """Map ``os_is_server`` to an OCSF device type."""
        return mappers.map_device_type(os_is_server)

    def build_operating_system(self, device: HolmDevice) -> OperatingSystem | None:
        """Map the Holm OS fields to an OCSF ``OperatingSystem`` object."""
        return mappers.build_operating_system(device.os_name, device.os_family)

    def build_network_interfaces(self, device: HolmDevice) -> list[NetworkInterface] | None:
        """Build the primary IPv4 and secondary IPv6 network interfaces."""
        return mappers.build_network_interfaces(device.network, device.hostname)

    def build_risk_level(self, max_severity: int | str | None) -> tuple[RiskLevelStr | None, RiskLevelId | None]:
        """Map the Holm ``max_severity`` of a device agent to an OCSF risk level."""
        if max_severity is None or max_severity == "":
            return None, None
        return self.MAX_SEVERITY_MAP.get(str(max_severity).strip().lower(), (None, None))

    def build_device(self, device: HolmDevice) -> Device:
        """Map a Holm device record to an OCSF ``Device`` object."""
        device_type, device_type_id = self.build_device_type(device.os_is_server)
        network = device.network
        risk_level, risk_level_id = self.build_risk_level(device.max_severity)

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
            risk_score=device.risk_score,
            risk_level=risk_level,
            risk_level_id=risk_level_id,
        )

    def build_net_asset_device(self, asset: HolmNetAsset) -> Device:
        """Map a Holm network asset to an OCSF ``Device`` object.

        Network assets are discovered by a scan instead of an agent, so they carry no
        MAC address, no OS family and no agent identifier.
        """
        device_type, device_type_id = mappers.map_net_asset_type(asset.type)
        risk_level, risk_level_id = mappers.map_severity_breakdown(asset.severity)

        return Device(
            type=device_type,
            type_id=device_type_id,
            uid=asset.uuid,
            name=asset.name,
            hostname=asset.hostname or "",
            os=mappers.build_operating_system_from_name(asset.operating_system),
            ip=asset.ip,
            desc=asset.details or None,
            created_time=self._to_epoch(asset.created),
            last_seen_time=self._to_epoch(asset.last_detected),
            is_managed=False,
            risk_score=asset.risk_score,
            risk_level=risk_level,
            risk_level_id=risk_level_id,
        )

    def _build_ocsf_model(self, device: Device, event_time: float) -> DeviceOCSFModel:
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
            device=device,
        )

    def map_fields(self, device: HolmDevice) -> DeviceOCSFModel:
        """Map a Holm device record to the OCSF Device Inventory Info model."""
        event_time = self._to_epoch(device.last_sync) or self._to_epoch(device.created)
        if event_time is None:
            raise ValueError(f"Device {device.uid} has neither last_sync nor created timestamp")

        return self._build_ocsf_model(self.build_device(device), event_time)

    def map_net_asset_fields(self, asset: HolmNetAsset) -> DeviceOCSFModel:
        """Map a Holm network asset to the OCSF Device Inventory Info model."""
        event_time = self._to_epoch(asset.last_detected) or self._to_epoch(asset.created)
        if event_time is None:
            raise ValueError(f"Network asset {asset.uuid} has neither last_detected nor created timestamp")

        return self._build_ocsf_model(self.build_net_asset_device(asset), event_time)

    def _fetch_device_pages(self, last_sync_from: str | None = None) -> Generator[HolmDevicePage, None, None]:
        """Fetch device pages, following the ``next`` URL until it is null."""
        url: str | None = f"{self.base_url}{self.DEVICES_ENDPOINT}"
        # The Holm API paginates with `limit`/`offset`; `page_size` is silently ignored.
        params: dict[str, int | str] | None = {
            "limit": self.DEFAULT_PAGE_SIZE,
            **({"last_sync_from": last_sync_from} if last_sync_from else {}),
        }

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

    def _fetch_net_asset_pages(self, last_detected_from: str | None = None) -> Generator[HolmNetAssetPage, None, None]:
        """Fetch network asset pages, following the ``next`` URL until it is null."""
        url: str | None = f"{self.base_url}{self.NET_ASSETS_ENDPOINT}"
        params: dict[str, int | str] | None = {
            "limit": self.DEFAULT_PAGE_SIZE,
            **({"last_detected_from": last_detected_from} if last_detected_from else {}),
        }

        try:
            while url and self.running:
                response = self.client.get(url, params=params, timeout=self.REQUEST_TIMEOUT)
                response.raise_for_status()

                page = HolmNetAssetPage.model_validate(response.json())
                self.log(
                    message=f"Fetched {len(page.results)} network assets (total {page.count})",
                    level="info",
                )

                yield page

                url = page.next
                # The `next` URL already carries the pagination query parameters.
                params = None
        except RequestException as error:
            self.log(message=f"Holm Security API request failed: {error}", level="error")
            raise

    def _collect_devices(self, cached_ids: set[str]) -> Generator[DeviceOCSFModel, None, None]:
        """Yield the agent-managed devices modified since the last run."""
        checkpoint = self.most_recent_last_sync
        checkpoint_dt: datetime | None = mappers.parse_datetime(checkpoint)

        max_dt: datetime | None = checkpoint_dt
        max_raw: str | None = checkpoint

        for page in self._fetch_device_pages(
            last_sync_from=checkpoint_dt.date().isoformat() if checkpoint_dt else None
        ):
            for device in page.results:
                device_dt = mappers.parse_datetime(device.last_sync)

                # Deduplicate: skip devices already pushed in a previous run.
                if device.uid in cached_ids:
                    self._skipped += 1
                    continue

                # Client-side checkpoint filter: skip devices not modified since last run.
                if checkpoint_dt is not None and device_dt is not None and device_dt <= checkpoint_dt:
                    self._skipped += 1
                    continue

                if device_dt is not None and (max_dt is None or device_dt > max_dt):
                    max_dt = device_dt
                    max_raw = device.last_sync

                try:
                    asset = self.map_fields(device)
                except (ValueError, ValidationError) as error:
                    self._skipped += 1
                    self.log(message=f"Skipping device {device.uid}: {error}", level="warning")
                    continue

                self._new_device_ids.add(device.uid)
                self._generated += 1
                yield asset

        # Only a complete traversal may advance the cursor: a run cut short by a
        # shutdown may have left older records unvisited.
        if self.running and max_raw and max_raw != checkpoint:
            self._latest_time = max_raw

    def _collect_net_assets(self, cached_ids: set[str]) -> Generator[DeviceOCSFModel, None, None]:
        """Yield the scanned network assets detected since the last run."""
        checkpoint = self.most_recent_net_asset_last_detected
        checkpoint_dt: datetime | None = mappers.parse_datetime(checkpoint)

        max_dt: datetime | None = checkpoint_dt
        max_raw: str | None = checkpoint

        for page in self._fetch_net_asset_pages(
            last_detected_from=checkpoint_dt.date().isoformat() if checkpoint_dt else None
        ):
            for net_asset in page.results:
                net_asset_dt = mappers.parse_datetime(net_asset.last_detected)

                if net_asset.uuid in cached_ids:
                    self._skipped += 1
                    continue

                if checkpoint_dt is not None and net_asset_dt is not None and net_asset_dt <= checkpoint_dt:
                    self._skipped += 1
                    continue

                if net_asset_dt is not None and (max_dt is None or net_asset_dt > max_dt):
                    max_dt = net_asset_dt
                    max_raw = net_asset.last_detected

                try:
                    asset = self.map_net_asset_fields(net_asset)
                except (ValueError, ValidationError) as error:
                    self._skipped += 1
                    self.log(message=f"Skipping network asset {net_asset.uuid}: {error}", level="warning")
                    continue

                self._new_device_ids.add(net_asset.uuid)
                self._generated += 1
                yield asset

        # Only a complete traversal may advance the cursor: a run cut short by a
        # shutdown may have left older records unvisited.
        if self.running and max_raw and max_raw != checkpoint:
            self._latest_net_asset_time = max_raw

    def get_assets(self) -> Generator[DeviceOCSFModel, None, None]:
        """Yield OCSF device assets for both agent devices and scanned network assets."""
        self._generated = 0
        self._skipped = 0
        cached_ids = self.seen_device_ids

        yield from self._collect_devices(cached_ids)
        yield from self._collect_net_assets(cached_ids)

        self.log(
            message=f"Asset generation complete - generated: {self._generated}, skipped: {self._skipped}",
            level="info",
        )

    def get_mapped_fields(self) -> dict[str, str]:
        """Return the Holm -> OCSF field mapping used for schema-change fingerprinting.

        Sources prefixed with ``net_assets.`` come from the scanned network asset
        inventory (``GET /v2/net-assets``).
        """
        return {
            "uid": "device.uid",
            "device_name": "device.name",
            "hostname": "device.hostname",
            "os_is_server": "device.type",
            "os_name": "device.os.name",
            "os_family": "device.os.type",
            "network.ip_address": "device.ip",
            "network.ip_address_v6": "device.network_interfaces.ip",
            "network.mac_address": "device.network_interfaces.mac",
            "created": "device.created_time",
            "last_sync": "device.last_seen_time",
            "max_severity": "device.risk_level",
            "risk_score": "device.risk_score",
            "net_assets.uuid": "device.uid",
            "net_assets.name": "device.name",
            "net_assets.hostname": "device.hostname",
            "net_assets.ip": "device.ip",
            "net_assets.type": "device.type",
            "net_assets.operating_system": "device.os.name",
            "net_assets.details": "device.desc",
            "net_assets.created": "device.created_time",
            "net_assets.last_detected": "device.last_seen_time",
            "net_assets.severity": "device.risk_level",
            "net_assets.risk_score": "device.risk_score",
        }

    def reset_checkpoint(self) -> None:
        """Clear the checkpoint and dedup cache so all assets are re-fetched from scratch."""
        with self.context as cache:
            cache.pop("most_recent_last_sync", None)
            cache.pop("most_recent_net_asset_last_detected", None)
            cache.pop("seen_device_ids", None)
        self._latest_time = None
        self._latest_net_asset_time = None
        self._new_device_ids = set()
        self.log(message="Checkpoint reset - all assets will be re-fetched on the next cycle", level="info")

    def update_checkpoint(self) -> None:
        if self._new_device_ids or self._latest_time or self._latest_net_asset_time:
            with self.context as cache:
                if self._latest_time:
                    cache["most_recent_last_sync"] = self._latest_time
                if self._latest_net_asset_time:
                    cache["most_recent_net_asset_last_detected"] = self._latest_net_asset_time
                existing_ids: set[str] = set(cache.get("seen_device_ids", []))
                existing_ids.update(self._new_device_ids)
                cache["seen_device_ids"] = list(existing_ids)
            self._new_device_ids = set()
            self.log(
                message=f"Checkpoint updated - last_sync={self._latest_time}, "
                f"net_asset_last_detected={self._latest_net_asset_time}, "
                f"total cached IDs={len(existing_ids)}",
                level="debug",
            )
        else:
            self.log(message="No checkpoint update needed", level="debug")
