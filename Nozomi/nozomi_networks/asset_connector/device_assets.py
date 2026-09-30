from collections.abc import Generator
from datetime import datetime, timezone
from functools import cached_property
from typing import Any

from pydantic.v1 import ValidationError
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.connector import AssetList
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.device import (
    Device,
    DeviceEnrichmentObject,
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

from nozomi_networks import NozomiModule
from nozomi_networks.asset_connector.client import NozomiQueryClient
from nozomi_networks.asset_connector.models import NozomiAsset


class NozomiDeviceAssetConnector(AssetConnector):
    """Fetch Nozomi Guardian/CMC assets (``query=assets``) as OCSF Device inventory."""

    module: NozomiModule

    # Configuration Constants
    PRODUCT_NAME: str = "Nozomi Networks"
    PRODUCT_VERSION: str = "1.0.0"
    METADATA_VERSION: str = "1.5.0"
    DEFAULT_PAGE_SIZE: int = 1000

    # OCSF Constants
    ACTIVITY_ID: int = 2
    ACTIVITY_NAME: str = "Collect"
    CATEGORY_NAME: str = "Discovery"
    CATEGORY_UID: int = 5
    CLASS_NAME: str = "Device Inventory Info"
    CLASS_UID: int = 5001
    TYPE_NAME: str = "Device Inventory Info: Collect"
    TYPE_UID: int = 500102

    # Nozomi asset type -> OCSF device type mapping
    DEVICE_TYPE_MAP: dict[str, tuple[DeviceTypeStr, DeviceTypeId]] = {
        "server": (DeviceTypeStr.SERVER, DeviceTypeId.SERVER),
        "workstation": (DeviceTypeStr.DESKTOP, DeviceTypeId.DESKTOP),
        "desktop": (DeviceTypeStr.DESKTOP, DeviceTypeId.DESKTOP),
        "computer": (DeviceTypeStr.DESKTOP, DeviceTypeId.DESKTOP),
        "laptop": (DeviceTypeStr.DESKTOP, DeviceTypeId.DESKTOP),
        "mobile": (DeviceTypeStr.MOBILE, DeviceTypeId.MOBILE),
        "smartphone": (DeviceTypeStr.MOBILE, DeviceTypeId.MOBILE),
        "tablet": (DeviceTypeStr.MOBILE, DeviceTypeId.MOBILE),
        "virtual": (DeviceTypeStr.VIRTUAL, DeviceTypeId.VIRTUAL),
        "vm": (DeviceTypeStr.VIRTUAL, DeviceTypeId.VIRTUAL),
        "firewall": (DeviceTypeStr.FIREWALL, DeviceTypeId.FIREWALL),
        "switch": (DeviceTypeStr.SWITCH, DeviceTypeId.SWITCH),
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("device_context.json", self._data_path)
        self._client: NozomiQueryClient | None = None
        self._latest_checkpoint: tuple[int, set[str]] | None = None
        self._push_failed = False

    @property
    def checkpoint(self) -> tuple[int | None, set[str]]:
        """Return the last collected ``created_at`` (epoch ms) and the IDs of the assets sharing it."""
        with self.context as cache:
            timestamp_ms = cache.get("most_recent_created_at_ms")
            ids = cache.get("most_recent_ids") or []
        return (int(timestamp_ms) if timestamp_ms is not None else None), set(ids)

    @cached_property
    def _version(self) -> str:
        return str(self.module.manifest.get("version", self.PRODUCT_VERSION))

    @cached_property
    def _slug(self) -> str:
        return str(self.module.manifest.get("slug", "nozomi"))

    @property
    def client(self) -> NozomiQueryClient:
        if self._client is None:
            default_headers = {
                "nn-app": f"sekoiaio-asset-connector/{self._slug}",
                "nn-app-version": self._version,
            }
            self._client = NozomiQueryClient(
                key_name=self.module.configuration.key_name,
                key_token=self.module.configuration.key_token,
                base_url=self.module.configuration.base_url,
                page_size=self.DEFAULT_PAGE_SIZE,
                default_headers=default_headers,
            )
        return self._client

    @cached_property
    def metadata(self) -> Metadata:
        return Metadata(
            product=Product(name=self.PRODUCT_NAME, version=self._version),
            version=self.METADATA_VERSION,
        )

    @staticmethod
    def _parse_epoch_ms(value: str | None) -> datetime | None:
        """Parse a Nozomi epoch-millisecond string into an aware datetime."""
        if not value:
            return None
        try:
            millis = int(value)
            if millis <= 0:
                return None
            return datetime.fromtimestamp(millis / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OverflowError, OSError):
            return None

    @staticmethod
    def extract_os_type(os_type: str | None) -> str:
        if not os_type:
            return "UNKNOWN"
        normalized = os_type.strip().upper()
        valid_types = {member.name for member in OSTypeStr}
        return normalized if normalized in valid_types else "OTHER"

    def build_operating_system(self, asset: NozomiAsset) -> OperatingSystem | None:
        if not asset.os:
            return None
        os_type = self.extract_os_type(asset.os)
        return OperatingSystem(name=asset.os, type=OSTypeStr[os_type], type_id=OSTypeId[os_type])

    def build_device_type(self, asset_type: str | None) -> tuple[DeviceTypeStr, DeviceTypeId]:
        if not asset_type:
            return DeviceTypeStr.UNKNOWN, DeviceTypeId.UNKNOWN
        return self.DEVICE_TYPE_MAP.get(asset_type.strip().lower(), (DeviceTypeStr.OTHER, DeviceTypeId.OTHER))

    def build_network_interfaces(self, asset: NozomiAsset) -> list[NetworkInterface] | None:
        """
        Build network interfaces from the asset IP and MAC lists.

        The API returns ``ip`` and ``mac_address`` as independent lists without any
        IP/MAC relationship. They are only paired when the asset has a single MAC
        (single-NIC device); otherwise IPs and MACs are exported as separate
        interfaces so that no MAC is lost and no association is invented.
        """
        ips = list(dict.fromkeys(ip for ip in asset.ip if ip))
        macs = list(dict.fromkeys(mac for mac in asset.mac_address if mac))
        if not ips and not macs:
            return None

        def interface(ip: str | None = None, mac: str | None = None) -> NetworkInterface:
            return NetworkInterface(
                hostname=asset.name,
                ip=ip,
                mac=mac,
                type=NetworkInterfaceTypeStr.WIRED,
                type_id=NetworkInterfaceTypeId.WIRED,
            )

        if len(macs) == 1 and ips:
            return [interface(ip=ip, mac=macs[0]) for ip in ips]

        return [interface(ip=ip) for ip in ips] + [interface(mac=mac) for mac in macs]

    def build_device(self, asset: NozomiAsset) -> Device:
        created = self._parse_epoch_ms(asset.created_at)
        last_seen = self._parse_epoch_ms(asset.last_activity_time)

        device_type, device_type_id = self.build_device_type(asset.type)
        vendor = asset.vendor or (asset.mac_vendor[0] if asset.mac_vendor else None)

        return Device(
            type=device_type,
            type_id=device_type_id,
            uid=asset.id,
            hostname=asset.name or asset.id,
            name=asset.name,
            os=self.build_operating_system(asset),
            ip=asset.ip[0] if asset.ip else None,
            network_interfaces=self.build_network_interfaces(asset),
            vendor_name=vendor,
            model=asset.product_name,
            created_time=created.timestamp() if created else None,
            first_seen_time=created.timestamp() if created else None,
            last_seen_time=last_seen.timestamp() if last_seen else None,
        )

    def build_enrichments(self, asset: NozomiAsset) -> list[DeviceEnrichmentObject] | None:
        enrichments: list[DeviceEnrichmentObject] = []

        if asset.firmware_version:
            enrichments.append(DeviceEnrichmentObject(name="firmware_version", value=asset.firmware_version))
        if asset.serial_number:
            enrichments.append(DeviceEnrichmentObject(name="serial_number", value=asset.serial_number))
        if asset.zones:
            enrichments.append(DeviceEnrichmentObject(name="zones", value=", ".join(asset.zones)))
        if asset.roles:
            enrichments.append(DeviceEnrichmentObject(name="roles", value=", ".join(asset.roles)))
        if asset.protocols:
            enrichments.append(DeviceEnrichmentObject(name="protocols", value=", ".join(asset.protocols)))
        if asset.levels:
            enrichments.append(DeviceEnrichmentObject(name="levels", value=", ".join(asset.levels)))

        return enrichments or None

    def map_fields(self, asset: NozomiAsset) -> DeviceOCSFModel:
        created = self._parse_epoch_ms(asset.created_at)
        event_time = (created or datetime.now(tz=timezone.utc)).timestamp()

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
            device=self.build_device(asset),
            enrichments=self.build_enrichments(asset),
        )

    def iterate_assets(self) -> Generator[list[NozomiAsset], None, None]:
        from_timestamp_ms, seen_ids = self.checkpoint

        self.log(
            f"Starting Nozomi asset iteration - Checkpoint: {from_timestamp_ms or 'None'}",
            level="info",
        )

        max_timestamp_ms = from_timestamp_ms
        max_ids = set(seen_ids)

        for assets in self.client.fetch_assets(from_timestamp_ms, exclude_ids=seen_ids):
            for asset in assets:
                created_ms = NozomiQueryClient._created_at_ms(asset)
                if created_ms is None:
                    continue
                if max_timestamp_ms is None or created_ms > max_timestamp_ms:
                    max_timestamp_ms = created_ms
                    max_ids = {asset.id}
                elif created_ms == max_timestamp_ms:
                    max_ids.add(asset.id)

            yield assets

        if max_timestamp_ms is not None:
            self._latest_checkpoint = (max_timestamp_ms, max_ids)

    def post_assets_to_api(self, assets: AssetList, asset_connector_api_url: str) -> dict[str, str] | None:
        """Push a batch and remember whether it made it through."""
        response: dict[str, str] | None = super().post_assets_to_api(assets, asset_connector_api_url)
        if response is None:
            # The batch was dropped: hold the checkpoint back so the next cycle collects it again.
            self._push_failed = True
        return response

    def asset_fetch_cycle(self) -> None:
        """Run a fetch cycle, then commit the checkpoint only if every batch was pushed."""
        self._latest_checkpoint = None
        self._push_failed = False
        super().asset_fetch_cycle()
        # The SDK only commits after each successful push, which misses the checkpoint when the
        # asset count is an exact multiple of batch_size. An interrupted cycle raises and never gets here.
        self.update_checkpoint()

    def update_checkpoint(self) -> None:
        if self._latest_checkpoint is None or self._push_failed:
            return
        timestamp_ms, ids = self._latest_checkpoint
        with self.context as cache:
            cache["most_recent_created_at_ms"] = timestamp_ms
            cache["most_recent_ids"] = sorted(ids)
        self.log(f"Checkpoint updated - New created_at: {timestamp_ms}", level="debug")

    def get_assets(self) -> Generator[DeviceOCSFModel, None, None]:
        self.log("Nozomi device asset generation started", level="info")

        generated = 0
        skipped = 0

        for assets in self.iterate_assets():
            for asset in assets:
                try:
                    yield self.map_fields(asset)
                    generated += 1
                except (ValidationError, KeyError, ValueError) as error:
                    skipped += 1
                    self.log(
                        f"Asset skipped - ID: {asset.id}, Reason: {error!s}",
                        level="warning",
                    )
                    continue

        self.log(
            f"Nozomi device asset generation completed - Generated: {generated}, Skipped: {skipped}",
            level="info",
        )
