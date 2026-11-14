import hashlib
from collections import Counter
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

from pydantic import ValidationError
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.connector import AssetList, DefaultAssetConnectorConfiguration
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.device import (
    Device,
    DeviceDataObject,
    DeviceEnrichmentObject,
    DeviceOCSFModel,
    DeviceTypeId,
    DeviceTypeStr,
    GeoLocation,
)
from sekoia_automation.asset_connector.models.ocsf.group import Group
from sekoia_automation.storage import PersistentJSON

from easyvista_modules.action_base import EasyVistaHttpMixin
from easyvista_modules.asset_connector.hostname import split_hostname
from easyvista_modules.asset_connector.models import EasyVistaAsset

KNOWN_DEVICES_KEY = "known_devices"
PAGE_SIZE = 100

METADATA = Metadata(product=Product(name="EasyVista Service Manager", vendor_name="EasyVista"), version="1.5.0")

# The default field set of GET /assets lacks NETWORK_IDENTIFIER
ASSET_FIELDS = tuple(EasyVistaAsset.model_fields)


class EasyVistaDeviceAssetConnectorConfiguration(DefaultAssetConnectorConfiguration):
    search: str | None = None


class EasyVistaDeviceAssetConnector(EasyVistaHttpMixin, AssetConnector):
    """
    Collect the devices of the EasyVista Service Manager asset inventory.

    GET /assets also returns licenses and contracts: only assets with a network identifier usable as
    hostname are devices. Removed or recycled assets are skipped.

    Dates follow the locale of the API user, so no date filter is used: every cycle lists all assets
    and yields only those whose OCSF output changed, tracked as a fingerprint per asset id.
    """

    configuration: EasyVistaDeviceAssetConnectorConfiguration

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("device_context.json", self.data_path)
        self._fingerprints: dict[str, str] = {}
        self._listing_complete = False
        self._pending = False
        self._skipped: Counter[str] = Counter()

    def error(self, message: str) -> None:
        # EasyVistaHttpMixin reports API errors here: an error ends the listing, the cycle keeps its checkpoint
        raise RuntimeError(message)

    @staticmethod
    def _timestamp(value: datetime | None) -> float | None:
        return value.timestamp() if value else None

    def map_fields(self, asset: EasyVistaAsset) -> DeviceOCSFModel | None:
        """Map an asset to an OCSF device, None when it has no usable hostname."""
        hostname, domain = split_hostname(asset.NETWORK_IDENTIFIER)
        if not hostname:
            return None

        is_server = asset.SERVER_TYPE_ID is not None
        catalog = asset.CATALOG_ASSET
        first_seen = self._timestamp(asset.INSTALLATION_DATE or asset.ENTRY_DATE)
        city = asset.LOCATION.CITY if asset.LOCATION else None
        email = asset.EMPLOYEE.E_MAIL if asset.EMPLOYEE else None
        fqdn = asset.NETWORK_IDENTIFIER if domain else None

        device = Device(
            type=DeviceTypeStr.SERVER if is_server else DeviceTypeStr.UNKNOWN,
            type_id=DeviceTypeId.SERVER if is_server else DeviceTypeId.UNKNOWN,
            uid=asset.ASSET_ID,
            hostname=hostname,
            domain=domain,
            name=asset.NETWORK_IDENTIFIER,
            desc=asset.ASSET_LABEL,
            uid_alt=asset.SERIAL_NUMBER or asset.ASSET_TAG,
            model=(catalog.ARTICLE_MODEL or catalog.SMBIOS_NAME) if catalog else None,
            location=GeoLocation(city=city) if city else None,
            groups=([Group(uid=asset.DEPARTMENT_ID, name=asset.DEPARTMENT_PATH)] if asset.DEPARTMENT_PATH else None),
            created_time=first_seen,
            first_seen_time=first_seen,
            last_seen_time=self._timestamp(asset.LAST_AUTOMATIC_DISCOVERY),
            is_managed=True,
        )

        enrichments = None
        if email or fqdn:
            data = DeviceDataObject(Users=[email] if email else None, Full_qualified_domain_name=fqdn)
            enrichments = [DeviceEnrichmentObject(name="compliance", value="hygiene", data=data)]

        return DeviceOCSFModel(
            activity_id=2,
            activity_name="Collect",
            category_name="Discovery",
            category_uid=5,
            class_name="Device Inventory Info",
            class_uid=5001,
            type_name="Device Inventory Info: Collect",
            type_uid=500102,
            severity="Informational",
            severity_id=1,
            time=self._timestamp(asset.LAST_UPDATE) or datetime.now(UTC).timestamp(),
            metadata=METADATA,
            device=device,
            enrichments=enrichments,
        )

    def _list_assets(self) -> Generator[EasyVistaAsset]:
        """
        Pages are linked by `@next` (EV Service Manager 2024.3+). Its URL drops the `fields` and `search`
        parameters, so only its `offset` is reused with the original parameters.
        """
        params: dict[str, Any] = {"max_rows": PAGE_SIZE, "fields": ",".join(ASSET_FIELDS)}
        if self.configuration.search:
            params["search"] = self.configuration.search

        while True:
            payload = self.get("/assets", params=params)
            for record in payload.get("records") or []:
                try:
                    yield EasyVistaAsset.model_validate(record)
                except ValidationError as error:
                    self._skipped["invalid"] += 1
                    self.log(f"Skipping invalid EasyVista asset {record.get('ASSET_ID')}: {error}", level="warning")
            if not self.running:
                return

            next_offset = parse_qs(urlsplit(payload.get("@next") or "").query).get("offset")
            if not next_offset or next_offset[0] == params.get("offset"):
                break
            params["offset"] = next_offset[0]
        self._listing_complete = True

    def get_assets(self) -> Generator[DeviceOCSFModel]:
        """Yield the devices that are new or changed since the previous cycle."""
        with self.context as cache:
            known: dict[str, str] = cache.get(KNOWN_DEVICES_KEY, {})
        self._fingerprints = {}
        self._listing_complete = False
        self._pending = False
        self._skipped.clear()
        changed = 0

        try:
            for asset in self._list_assets():
                if asset.is_removed:
                    self._skipped["removed"] += 1
                    continue
                try:
                    device = self.map_fields(asset)
                except ValidationError as error:
                    self._skipped["unmappable"] += 1
                    self.log(f"Skipping EasyVista asset {asset.ASSET_ID}: {error}", level="warning")
                    continue
                if device is None:
                    self._skipped["no_hostname"] += 1
                    continue

                # `time` falls back to now: excluded so an unchanged device keeps its fingerprint
                fingerprint = hashlib.sha256(device.model_dump_json(exclude={"time"}).encode()).hexdigest()[:16]
                # Set before the yield: the SDK checkpoints a full batch before resuming the generator
                self._fingerprints[asset.ASSET_ID] = fingerprint
                if known.get(asset.ASSET_ID) != fingerprint:
                    changed += 1
                    self._pending = True
                    yield device
        except Exception as error:
            self.log_exception(error, message="Failed to list EasyVista assets")

        # No push follows when every yielded device was already checkpointed: save the snapshot here
        if self._listing_complete and not self._pending:
            self.update_checkpoint()
        self.log(
            f"{changed} new or changed devices out of {len(self._fingerprints)} listed, skipped: "
            f"{self._skipped['removed']} removed, {self._skipped['no_hostname']} without network identifier, "
            f"{self._skipped['invalid']} invalid, {self._skipped['unmappable']} unmappable",
            level="info",
        )

    def post_assets_to_api(self, assets: AssetList, asset_connector_api_url: str) -> dict[str, str] | None:
        """Push a batch; on failure forget its fingerprints so a later checkpoint does not mark them known."""
        response = super().post_assets_to_api(assets, asset_connector_api_url)
        if response is None:
            for item in assets.items:
                self._fingerprints.pop(item.device.uid, None)  # type: ignore[union-attr]
        return response

    def update_checkpoint(self) -> None:
        """Save the fingerprints of the devices listed so far."""
        # ponytail: rewrites the whole cache after each pushed batch, O(devices x batches) on a first cycle;
        # persist once per cycle if large inventories make it slow (a crash then re-pushes the cycle).
        with self.context as cache:
            # Once every asset was listed, the snapshot replaces the cache and drops deleted devices
            known = {} if self._listing_complete else cache.get(KNOWN_DEVICES_KEY, {})
            cache[KNOWN_DEVICES_KEY] = {**known, **self._fingerprints}
        self._pending = False

    def reset_checkpoint(self) -> None:
        """Forget every fingerprint so the next cycle pushes all devices."""
        with self.context as cache:
            cache.pop(KNOWN_DEVICES_KEY, None)
        self._fingerprints = {}

    def get_mapped_fields(self) -> dict[str, str]:
        """Return the EasyVista -> OCSF field mapping, mirroring device_mapping.yml."""
        return {
            "ASSET_ID": "device.uid",
            "NETWORK_IDENTIFIER": (
                "device.hostname, device.domain, device.name, enrichments.data.Full_qualified_domain_name"
            ),
            "ASSET_LABEL": "device.desc",
            "SERIAL_NUMBER": "device.uid_alt",
            "ASSET_TAG": "device.uid_alt",
            "SERVER_TYPE_ID": "device.type_id",
            "CATALOG_ASSET.ARTICLE_MODEL": "device.model",
            "CATALOG_ASSET.SMBIOS_NAME": "device.model",
            "LOCATION.CITY": "device.location.city",
            "DEPARTMENT_ID": "device.groups.uid",
            "DEPARTMENT_PATH": "device.groups.name",
            "INSTALLATION_DATE": "device.created_time, device.first_seen_time",
            "ENTRY_DATE": "device.created_time, device.first_seen_time",
            "LAST_AUTOMATIC_DISCOVERY": "device.last_seen_time",
            "LAST_UPDATE": "time",
            "EMPLOYEE.E_MAIL": "enrichments.data.Users",
        }
