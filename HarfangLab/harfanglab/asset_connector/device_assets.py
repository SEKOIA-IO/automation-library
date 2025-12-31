from functools import cached_property
from collections.abc import Generator
from typing import Any, Optional
from urllib.parse import urljoin
from datetime import timedelta, datetime

from dateutil.parser import isoparse
from requests.exceptions import RequestException

from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import (
    Metadata,
    Product,
)
from sekoia_automation.asset_connector.models.ocsf.device import (
    DeviceOCSFModel,
    OperatingSystem,
    Device,
    OSTypeStr,
    DeviceTypeId,
    DeviceTypeStr,
    OSTypeId,
    NetworkInterface,
    NetworkInterfaceTypeStr,
    NetworkInterfaceTypeId,
    DeviceDataObject,
    EncryptionObject,
    DeviceEnrichmentObject,
)
from sekoia_automation.storage import PersistentJSON

from harfanglab.helpers import handle_uri
from harfanglab.client import ApiClient
from harfanglab.models import HarfanglabModule


class HarfanglabAssetConnector(AssetConnector):

    module: HarfanglabModule

    # Configuration Constants
    AGENT_ENDPOINT: str = "/api/data/endpoint/Agent"
    DEVICE_ORDERING_FIELD: str = "firstseen"
    PRODUCT_NAME: str = "Harfanglab EDR"
    PRODUCT_VERSION: str = "24.12"
    METADATA_VERSION: str = "1.5.0"
    DEFAULT_LIMIT: int = 1000

    # OCSF Constants
    ACTIVITY_ID: int = 2
    ACTIVITY_NAME: str = "Collect"
    CATEGORY_NAME: str = "Discovery"
    CATEGORY_UID: int = 5
    CLASS_NAME: str = "Asset"
    CLASS_UID: int = 5001
    TYPE_NAME: str = "Software Inventory Info: Collect"
    TYPE_UID: int = 500102

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self._latest_time: str | None = None

    @property
    def most_recent_date_seen(self) -> str | None:
        with self.context as cache:
            return cache.get("most_recent_date_seen")

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(token=self.module.configuration.api_token, instance_url=self.base_url)

    @cached_property
    def base_url(self) -> str:
        return handle_uri(self.module.configuration.url)

    @staticmethod
    def extract_timestamp(asset: dict[str, Any]) -> datetime:
        if "firstseen" not in asset:
            raise KeyError("Required field 'firstseen' is missing from asset")

        try:
            return isoparse(asset["firstseen"])
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid date format for 'firstseen': {asset.get('firstseen')}") from e

    @staticmethod
    def extract_os_type(os_type: str | None) -> str:
        if not os_type:
            return "UNKNOWN"

        normalized = os_type.strip().upper()
        valid_types = {member.name for member in OSTypeStr}

        if normalized not in valid_types:
            return "OTHER"

        return normalized

    def _validate_asset_data(self, asset: dict[str, Any]) -> None:
        required_fields = ["id", "hostname", "firstseen"]
        missing_fields = [field for field in required_fields if field not in asset]

        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

    @cached_property
    def metadata(self) -> Metadata:
        return Metadata(
            product=Product(name=self.PRODUCT_NAME, version=self.PRODUCT_VERSION), version=self.METADATA_VERSION
        )

    def build_operating_system(self, os_product_type: Optional[str], os_type: Optional[str]) -> OperatingSystem:
        os_type = self.extract_os_type(os_type)
        return OperatingSystem(name=os_product_type, type=OSTypeStr[os_type], type_id=OSTypeId[os_type])

    def build_network_interface(self, asset: dict[str, Any]) -> NetworkInterface | None:
        ip = asset.get("ipaddress")
        subnet_info = asset.get("subnet", {})

        if not ip and not subnet_info:
            return None

        # Determine interface type based on available data
        interface_type = NetworkInterfaceTypeStr.WIRED
        interface_type_id = NetworkInterfaceTypeId.WIRED

        return NetworkInterface(
            hostname=asset.get("hostname"),
            ip=ip,
            mac=subnet_info.get("gateway_macaddress") if subnet_info else None,
            name=subnet_info.get("name") if subnet_info else None,
            type=interface_type,
            type_id=interface_type_id,
            uid=subnet_info.get("id") if subnet_info else None,
        )

    def build_device(self, asset: dict[str, Any]) -> Device:
        asset_id = asset.get("id", "unknown")

        os_type = asset.get("ostype")
        os_product_type = asset.get("osproducttype")

        first_seen_time = None
        last_seen_time = None
        boot_time = None
        created_time = None

        try:
            if asset.get("firstseen"):
                first_seen_time = isoparse(asset["firstseen"]).timestamp()
            if asset.get("lastseen"):
                last_seen_time = isoparse(asset["lastseen"]).timestamp()
            if asset.get("machine_boottime"):
                boot_time_dt = isoparse(asset["machine_boottime"])
                boot_time = boot_time_dt.isoformat()
            if asset.get("installdate"):
                created_time = datetime.fromisoformat(asset["installdate"]).timestamp()
        except (ValueError, TypeError) as e:
            self.log(f"Error parsing timestamps for asset {asset_id}: {e}", level="warning")

        network_interfaces = []
        network_interface = self.build_network_interface(asset)
        if network_interface:
            network_interfaces.append(network_interface)

        return Device(
            type_id=DeviceTypeId.DESKTOP,
            type=DeviceTypeStr.DESKTOP,
            uid=asset["id"],
            os=self.build_operating_system(os_product_type, os_type),
            hostname=asset["hostname"],
            domain=asset.get("domainname"),
            ip=asset.get("ipaddress"),
            subnet=asset.get("ipmask"),
            network_interfaces=network_interfaces if network_interfaces else None,
            first_seen_time=first_seen_time,
            last_seen_time=last_seen_time,
            boot_time=boot_time,
            created_time=created_time,
            desc=asset.get("description"),
            is_managed=asset.get("policy") is not None,
            is_trusted=asset.get("has_valid_password"),
            hypervisor=None,
            region=None,
            model=asset.get("producttype"),
            vendor_name="HarfangLab",
        )

    def build_enrichments(self, asset: dict[str, Any]) -> DeviceEnrichmentObject | None:
        policy = asset.get("policy", {})

        # Extract firewall status
        firewall_enabled = policy.get("windows_self_protection_feature_firewall")
        firewall_status = "Enabled" if firewall_enabled else "Disabled" if firewall_enabled is not None else None

        # Extract encryption info
        encrypted_count = asset.get("encrypted_disk_count", 0)
        total_count = asset.get("disk_count", 0)

        encryption_obj = None
        if total_count > 0:
            encryption_obj = EncryptionObject(
                partitions={f"disk_{i}": "Enabled" if i < encrypted_count else "Disabled" for i in range(total_count)}
            )

        if not firewall_status and not encryption_obj:
            return None

        device_data_object = DeviceDataObject(
            Firewall_status=firewall_status,
            Storage_encryption=encryption_obj,
            Users=None,
        )

        enrichment_object = DeviceEnrichmentObject(name="compliance", value="hygiene", data=device_data_object)

        return enrichment_object

    def map_fields(self, asset: dict[str, Any]) -> DeviceOCSFModel:
        try:
            self._validate_asset_data(asset)
            asset_id = asset.get("id", "unknown")
            hostname = asset.get("hostname", "Unknown")

            self.log(f"Mapping asset - ID: {asset_id}, Hostname: {hostname}", level="debug")

            enrichments = self.build_enrichments(asset)

            return DeviceOCSFModel(
                activity_id=self.ACTIVITY_ID,
                activity_name=self.ACTIVITY_NAME,
                category_name=self.CATEGORY_NAME,
                category_uid=self.CATEGORY_UID,
                class_name=self.CLASS_NAME,
                class_uid=self.CLASS_UID,
                type_name=self.TYPE_NAME,
                type_uid=self.TYPE_UID,
                time=self.extract_timestamp(asset).timestamp(),
                metadata=self.metadata,
                device=self.build_device(asset),
                enrichments=[enrichments] if enrichments else None,
            )
        except (KeyError, ValueError) as e:
            asset_id = asset.get("id", "unknown")
            self.log(f"Failed to map asset - ID: {asset_id}, Error: {str(e)}", level="error")
            raise

    def _fetch_devices(self, from_date: str | None) -> Generator[list[dict[str, Any]], None, None]:
        self.log(f"Fetching devices from Harfanglab API - Start date: {from_date or 'beginning'}", level="info")

        devices_url = urljoin(self.base_url, self.AGENT_ENDPOINT)
        params: dict[str, str | int] = {
            "ordering": self.DEVICE_ORDERING_FIELD,
            "limit": self.DEFAULT_LIMIT,
        }

        if from_date:
            params["firstseen"] = from_date

        try:
            device_response = self.client.get(devices_url, params=params)
            device_response.raise_for_status()

            page_number = 1

            while self.running:
                devices = device_response.json()
                count = devices.get("count", 0)
                results_count = len(devices.get("results", []))

                self.log(
                    f"Retrieved page {page_number} - Total count: {count}, Results in page: {results_count}",
                    level="info",
                )

                if not devices or count == 0:
                    self.log("No more devices to fetch", level="info")
                    return

                yield devices.get("results", [])

                next_page = devices.get("next")
                if not next_page:
                    self.log(f"Pagination complete - Total pages processed: {page_number}", level="info")
                    return

                page_number += 1
                next_page_url = urljoin(self.base_url, next_page)

                self.log(f"Fetching next page {page_number} - URL: {next_page_url}", level="debug")

                device_response = self.client.get(next_page_url)
                device_response.raise_for_status()

        except RequestException as e:
            self.log(f"API request failed - URL: {devices_url}, Error: {str(e)}", level="error")
            raise

    def iterate_devices(self) -> Generator[list[dict[str, Any]], None, None]:
        orig_date = isoparse(self.most_recent_date_seen) if self.most_recent_date_seen else None
        max_date: datetime | None = None

        self.log(f"Starting device iteration - Checkpoint date: {self.most_recent_date_seen or 'None'}", level="info")

        device_count = 0

        try:

            for devices in self._fetch_devices(from_date=self.most_recent_date_seen):
                if not devices:
                    continue

                device_count += len(devices)

                last_device = max(devices, key=self.extract_timestamp)
                last_ts = self.extract_timestamp(last_device)
                candidate = last_ts + timedelta(microseconds=1)

                if max_date is None or candidate > max_date:
                    max_date = candidate

                yield devices

            self.log(f"Device iteration complete - Total devices processed: {device_count}", level="info")

            if max_date and (orig_date is None or max_date > orig_date):
                self.log(
                    f"Updating checkpoint - New date: {max_date.isoformat()}, Previous date: {orig_date.isoformat() if orig_date else 'None'}",
                    level="info",
                )
                self._latest_time = max_date.isoformat()

        except Exception as e:
            self.log(f"Device iteration failed - Error: {str(e)}, Devices processed: {device_count}", level="error")
            raise

    def update_checkpoint(self) -> None:
        if self._latest_time:
            with self.context as cache:
                cache["most_recent_date_seen"] = self._latest_time

            self.log(f"Checkpoint updated successfully - New timestamp: {self._latest_time}", level="debug")
        else:
            self.log("No checkpoint update needed - No new timestamp available", level="debug")

    def get_assets(self) -> Generator[DeviceOCSFModel, None, None]:
        self.log(f"Asset generation started - Data path: {self._data_path.absolute()}", level="info")

        assets_generated = 0
        assets_skipped = 0

        try:
            for devices in self.iterate_devices():
                for device in devices:
                    try:
                        yield self.map_fields(device)
                        assets_generated += 1
                    except (KeyError, ValueError) as e:
                        assets_skipped += 1
                        device_id = device.get("id", "unknown")
                        device_hostname = device.get("hostname", "unknown")

                        self.log(
                            f"Asset skipped - ID: {device_id}, Hostname: {device_hostname}, Reason: {str(e)}",
                            level="warning",
                        )
                        continue

            self.log(
                f"Asset generation completed - Total generated: {assets_generated}, Skipped: {assets_skipped}",
                level="info",
            )

        except Exception as e:
            self.log(
                f"Asset generation failed - Generated: {assets_generated}, Skipped: {assets_skipped}, Error: {str(e)}",
                level="error",
            )
            raise
