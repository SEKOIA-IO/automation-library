from functools import cached_property
from collections.abc import Generator
from typing import Literal
from datetime import datetime

from dateutil.parser import isoparse
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.connector import AssetList
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

from crowdstrike_falcon.asset_connectors.crowdstrike_device_model import CrowdStrikeDevice
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
        self._push_failed = False
        self._groups_cache: dict[str, Group] = {}
        self._groups_fetch_disabled = False

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

    def get_device_os(self, device: CrowdStrikeDevice) -> OperatingSystem:
        """
        Determine the operating system from device data.
        Maps platform_name to OCSF OS type and includes version info.
        """
        platform_name = device.platform_name
        os_version = device.os_version

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

    def get_device_type(self, device: CrowdStrikeDevice) -> tuple[DeviceTypeId, DeviceTypeStr]:
        """
        Determine the device type from product_type_desc.
        Maps CrowdStrike product types to OCSF device types.
        """
        product_type_desc = device.product_type_desc or ""
        device_type = product_type_desc.lower()

        type_mapping: dict[str, tuple[DeviceTypeId, DeviceTypeStr]] = {
            "server": (DeviceTypeId.SERVER, DeviceTypeStr.SERVER),
            "workstation": (DeviceTypeId.DESKTOP, DeviceTypeStr.DESKTOP),
            "desktop": (DeviceTypeId.DESKTOP, DeviceTypeStr.DESKTOP),
            "laptop": (DeviceTypeId.DESKTOP, DeviceTypeStr.DESKTOP),
            "mobile": (DeviceTypeId.MOBILE, DeviceTypeStr.MOBILE),
            "tablet": (DeviceTypeId.MOBILE, DeviceTypeStr.MOBILE),
            "phone": (DeviceTypeId.MOBILE, DeviceTypeStr.MOBILE),
            "virtual": (DeviceTypeId.VIRTUAL, DeviceTypeStr.VIRTUAL),
        }

        for key, (type_id, type_str) in type_mapping.items():
            if key in device_type:
                return type_id, type_str

        return DeviceTypeId.UNKNOWN, DeviceTypeStr.UNKNOWN

    def get_firewall_status(self, device: CrowdStrikeDevice) -> Literal["Disabled", "Enabled"]:
        """
        Determine firewall status from device policies.
        """
        firewall_policy = device.device_policies.get("firewall")
        if firewall_policy and firewall_policy.applied:
            return "Enabled"
        return "Disabled"

    def get_network_interfaces(self, device: CrowdStrikeDevice) -> list[NetworkInterface] | None:
        """
        Extract network interfaces from device data.
        Creates interfaces for local IP, external IP, and connection IP.
        """
        interfaces: list[NetworkInterface] = []

        local_ip = device.local_ip
        mac_address = device.mac_address
        hostname = device.hostname

        if local_ip or mac_address:
            interfaces.append(
                NetworkInterface(
                    hostname=hostname,
                    ip=local_ip,
                    mac=self.normalize_mac_address(mac_address),
                    name="primary",
                )
            )

        connection_ip = device.connection_ip
        connection_mac = device.connection_mac_address

        if connection_ip and connection_ip != local_ip:
            interfaces.append(
                NetworkInterface(
                    ip=connection_ip,
                    mac=self.normalize_mac_address(connection_mac),
                    name="connection",
                )
            )

        return interfaces if interfaces else None

    def fetch_groups(self, group_ids: list[str]) -> None:
        """
        Fetch, in a single request, the details of the groups that are not cached yet.

        The details are unavailable when the API client misses the `Host groups: Read` scope.
        In that case, the fetching is disabled for the remaining of the cycle to avoid
        repeating a request that is known to fail for every device of the batch.
        """
        if self._groups_fetch_disabled:
            return

        # deduplicate the identifiers, keeping their order, and drop the already cached ones
        missing_ids = [
            group_id for group_id in dict.fromkeys(group_ids) if group_id and group_id not in self._groups_cache
        ]

        if not missing_ids:
            return

        try:
            for group_info in self.client.get_host_groups(missing_ids):
                group_id = group_info.get("id")
                if not group_id:
                    continue

                self._groups_cache[group_id] = Group(
                    uid=group_id,
                    name=group_info.get("name") or "Unknown",
                    desc=group_info.get("description") or None,
                )
        except Exception as e:
            self._groups_fetch_disabled = True
            self.log(
                f"Failed to fetch group details: {e}. ",
                level="warning",
            )

    def get_groups(self, device: CrowdStrikeDevice) -> list[Group] | None:
        """
        Extract groups from device data and fetch details from API.

        Resolved groups are cached for the whole fetch cycle: a tenant has a handful of
        host groups but tens of thousands of devices, and looking them up per device
        turns the run into one extra API call per device.
        """
        raw_groups = [group_id for group_id in device.groups or [] if group_id]
        if not raw_groups:
            return None

        unresolved = [group_id for group_id in raw_groups if group_id not in self._groups_cache]
        if unresolved:
            try:
                for group_info in self.client.get_host_groups(unresolved):
                    group_id = group_info.get("id")
                    if group_id:
                        self._groups_cache[group_id] = Group(
                            uid=group_id,
                            name=group_info.get("name", "Unknown"),
                            desc=group_info.get("description") or None,
                        )
            except Exception as e:
                self.log(f"Failed to fetch group details: {e}", level="warning")

            # Fall back on the identifier for whatever the API did not return, and cache
            # that too so a missing scope does not retry (and re-log) on every device.
            for group_id in unresolved:
                self._groups_cache.setdefault(group_id, Group(uid=group_id, name=group_id))

        return [self._groups_cache[group_id] for group_id in raw_groups]

    def get_location(self, device: CrowdStrikeDevice) -> GeoLocation | None:
        """
        Extract geographic location from device data.
        Uses zone_group for region information.
        """
        zone_group = device.zone_group
        if zone_group:
            return GeoLocation(country=zone_group[:2].upper() if len(zone_group) >= 2 else None)
        return None

    def get_organization(self, device: CrowdStrikeDevice) -> Organization | None:
        """
        Extract organization info from device data.
        Uses CID and service provider account info.
        """
        cid = device.cid

        if cid:
            return Organization(
                uid=cid,
                name=device.service_provider or "Unknown",
            )
        return None

    def is_device_compliant(self, device: CrowdStrikeDevice) -> bool | None:
        """
        Determine if device is compliant based on policies and status.
        """
        status = device.status
        rfm = device.reduced_functionality_mode
        containment = device.filesystem_containment_status

        # Device is compliant if status is normal, not in RFM, and not contained
        if status == "normal" and rfm == "no" and containment == "normal":
            return True
        elif status or rfm or containment:
            return False
        return None

    def get_enrichments(self, device: CrowdStrikeDevice) -> list[DeviceEnrichmentObject]:
        """
        Create enrichment objects with additional CrowdStrike-specific data.
        """
        enrichments: list[DeviceEnrichmentObject] = []

        users = [device.last_login_user] if device.last_login_user else None
        fqdn = None
        if device.hostname and device.machine_domain:
            fqdn = f"{device.hostname}.{device.machine_domain}"

        enrichments.append(
            DeviceEnrichmentObject(
                name="compliance",
                value="hygiene",
                data=DeviceDataObject(
                    Firewall_status=self.get_firewall_status(device),
                    Users=users,
                    Full_qualified_domain_name=fqdn,
                ),
            )
        )

        return enrichments

    def map_device_fields(self, device: CrowdStrikeDevice) -> DeviceOCSFModel | None:
        """
        Map Crowdstrike device fields to OCSF device model.
        Extracts maximum fields from CrowdStrike API response.
        """
        device_id = device.device_id
        hostname = device.hostname

        if not device_id:
            self.log(f"Skipping device: missing device_id. Data: {device}", level="warning")
            return None

        if not hostname:
            self.log(f"Skipping device {device_id}: missing hostname", level="warning")
            return None

        # Metadata
        product = Product(name=self.PRODUCT_NAME, version=self.PRODUCT_VERSION)
        metadata = Metadata(product=product, version=self.OCSF_VERSION)

        # Device attributes
        device_os = self.get_device_os(device)
        type_id, type_str = self.get_device_type(device)

        # Timestamps
        first_seen = device.first_seen
        last_seen = device.last_seen
        modified_timestamp = device.modified_timestamp
        agent_local_time = device.agent_local_time

        # Create Device object with all available fields
        crowdstrike_device = Device(
            # Required fields
            uid=device_id,
            hostname=hostname,
            type_id=type_id,
            type=type_str,
            # Operating System
            os=device_os,
            # Network
            ip=device.external_ip,
            network_interfaces=self.get_network_interfaces(device),
            subnet=device.default_gateway_ip,
            # Identity
            uid_alt=device.serial_number,
            domain=device.machine_domain or None,
            name=hostname,
            # Timestamps
            first_seen_time=self.parse_timestamp(first_seen),
            last_seen_time=self.parse_timestamp(last_seen),
            created_time=self.parse_timestamp(first_seen),
            boot_time=self.parse_timestamp(agent_local_time),
            # Hardware
            model=device.system_product_name,
            vendor_name=device.system_manufacturer,
            hypervisor=device.bios_manufacturer,
            desc=device.product_type_desc,
            # Cloud/Virtual
            region=device.zone_group,
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

    def post_assets_to_api(self, assets: AssetList, asset_connector_api_url: str) -> dict[str, str] | None:
        """Push a batch and remember whether it made it through."""
        response = super().post_assets_to_api(assets, asset_connector_api_url)
        if response is None:
            # The batch was dropped, so the devices it carried were never ingested: hold
            # the checkpoint back so the next cycle walks the whole listing again.
            self._push_failed = True
        return response

    def asset_fetch_cycle(self) -> None:
        """Run a fetch cycle, then commit the checkpoint if it collected everything."""
        super().asset_fetch_cycle()
        # Every batch of the cycle has been pushed by now, so this is the first moment we
        # know the run was complete. An interrupted cycle raises and never gets here.
        self.update_checkpoint()

    def update_checkpoint(self) -> None:
        """Update the checkpoint with the latest device ID."""
        self.log("Updating the device id !!", level="info")
        if self._latest_id is None or self._push_failed:
            return
        with self.context as cache:
            cache["most_recent_device_id"] = self._latest_id
            self.log(f"Device id was updated to {self._latest_id}", level="info")

    def next_devices_batch(self, uuids_batch: list[str]) -> Generator[CrowdStrikeDevice, None, None]:
        """
        Fetch the information of a batch of devices, with the details of their groups.
        """
        devices = [
            CrowdStrikeDevice.model_validate(device_info) for device_info in self.client.get_devices_infos(uuids_batch)
        ]

        self.fetch_groups([group_id for device in devices for group_id in device.groups])

        yield from devices

    def next_devices(self) -> Generator[CrowdStrikeDevice, None, None]:
        """
        Generator that yields device information from CrowdStrike API.
        Uses pagination and checkpoint to fetch only new devices.

        The checkpoint is only advanced once the whole listing has been walked. The SDK
        calls `update_checkpoint` after every batch it pushes, so remembering the newest
        device id up front would make any interruption of the run (pod restart, API
        error, rate limit) skip every device it had not reached yet, forever.
        """
        last_first_uuid = self.most_recent_device_id
        newest_uuid: str | None = None
        uuids_batch: list[str] = []

        # Nothing is collected yet: the pushes happening during this walk must not commit
        # a checkpoint.
        self._latest_id = None
        self._push_failed = False

        for idx, device_uuid in enumerate(self.client.list_devices_uuids(limit=self.LIMIT, sort="first_seen.desc")):
            if idx == 0:
                if device_uuid == last_first_uuid:
                    self.log("No device has been added !!", level="info")
                    return
                newest_uuid = device_uuid

            # Stop before the last seen device id
            if last_first_uuid and device_uuid == last_first_uuid:
                break

            uuids_batch.append(device_uuid)

            if len(uuids_batch) >= self.LIMIT:
                self.log(f"Found {len(uuids_batch)} devices !!", level="info")
                yield from self.next_devices_batch(uuids_batch)
                uuids_batch = []

        if uuids_batch:
            self.log(f"Found {len(uuids_batch)} devices in the last batch!!", level="info")
            yield from self.next_devices_batch(uuids_batch)

        # The whole listing was walked: remember where we stopped. It is committed at the
        # end of the cycle, once every batch has been pushed.
        self._latest_id = newest_uuid

    def get_assets(self) -> Generator[DeviceOCSFModel, None, None]:
        """
        Main generator that yields OCSF-formatted device assets.
        """
        self.log("Start the getting assets generator !!", level="info")

        # reset the group details collected in the previous cycle
        self._groups_cache = {}
        self._groups_fetch_disabled = False

        for device in self.next_devices():
            mapped = self.map_device_fields(device)
            if mapped is not None:  # pragma: no branch
                yield mapped
