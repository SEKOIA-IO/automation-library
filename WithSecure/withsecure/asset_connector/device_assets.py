import ipaddress
from collections.abc import Generator
from datetime import UTC, datetime
from functools import cached_property
from typing import Any, ClassVar, Literal

from pydantic import ValidationError
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.device import (
    Device,
    DeviceDataObject,
    DeviceEnrichmentObject,
    DeviceOCSFModel,
    DeviceTypeId,
    DeviceTypeStr,
    EncryptionObject,
    NetworkInterface,
    OperatingSystem,
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.asset_connector.models.ocsf.group import Group
from sekoia_automation.asset_connector.models.ocsf.organization import Organization
from sekoia_automation.storage import PersistentJSON

from withsecure import WithSecureModule
from withsecure.asset_connector.models import WithSecureDevice
from withsecure.client import ApiClient
from withsecure.constants import API_LIST_DEVICES_PAGE_SIZE, API_LIST_DEVICES_URL, API_TIMEOUT
from withsecure.helpers import human_readable_api_exception

IPInterface = ipaddress.IPv4Interface | ipaddress.IPv6Interface


class WithSecureDeviceAssetConnector(AssetConnector):
    """
    Collects the active devices of the WithSecure Elements organization of the API client.
    """

    module: WithSecureModule

    PRODUCT_NAME: str = "WithSecure Elements"
    PRODUCT_VENDOR: str = "WithSecure"
    OCSF_VERSION: str = "1.6.0"

    # OCSF constants
    ACTIVITY_ID: int = 2
    ACTIVITY_NAME: str = "Collect"
    CATEGORY_NAME: str = "Discovery"
    CATEGORY_UID: int = 5
    CLASS_NAME: str = "Device Inventory Info"
    CLASS_UID: int = 5001
    TYPE_NAME: str = "Device Inventory Info: Collect"
    TYPE_UID: int = 500102

    SERVER_PRODUCT_VARIANTS: frozenset[str] = frozenset(
        {"serversecurity", "serverprotection_premium", "serverprotection_premium_rdr", "rdr_server"}
    )

    # first matching keyword of the lowercased OS name wins
    OS_KEYWORDS: tuple[tuple[str, OSTypeStr, OSTypeId], ...] = (
        ("windows", OSTypeStr.WINDOWS, OSTypeId.WINDOWS),
        ("ipados", OSTypeStr.IPADOS, OSTypeId.IPADOS),
        ("ios", OSTypeStr.IOS, OSTypeId.IOS),
        ("android", OSTypeStr.ANDROID, OSTypeId.ANDROID),
        ("mac", OSTypeStr.MACOS, OSTypeId.MACOS),
        ("linux", OSTypeStr.LINUX, OSTypeId.LINUX),
        ("ubuntu", OSTypeStr.LINUX, OSTypeId.LINUX),
        ("debian", OSTypeStr.LINUX, OSTypeId.LINUX),
        ("red hat", OSTypeStr.LINUX, OSTypeId.LINUX),
        ("rhel", OSTypeStr.LINUX, OSTypeId.LINUX),
        ("centos", OSTypeStr.LINUX, OSTypeId.LINUX),
        ("suse", OSTypeStr.LINUX, OSTypeId.LINUX),
        ("rocky", OSTypeStr.LINUX, OSTypeId.LINUX),
        ("alma", OSTypeStr.LINUX, OSTypeId.LINUX),
        ("oracle", OSTypeStr.LINUX, OSTypeId.LINUX),
        ("fedora", OSTypeStr.LINUX, OSTypeId.LINUX),
    )

    # "...Ok", "disabledWs" and "disabledMacOs" states are not documented enough to tell
    # whether another firewall protects the device: they are left unknown.
    FIREWALL_STATES: ClassVar[dict[str, Literal["Enabled", "Disabled"]]] = {
        "enabled": "Enabled",
        "disabled": "Disabled",
        "disabledByGpo": "Disabled",
    }

    COMPLIANCE_STATES: ClassVar[dict[str, bool]] = {
        "allOk": True,
        "warning": False,
        "critical": False,
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("device_context.json", self._data_path)
        self._latest_time: str | None = None

    @property
    def most_recent_date_seen(self) -> str | None:
        with self.context as cache:
            return cache.get("most_recent_date_seen")

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            client_id=self.module.configuration.client_id,
            secret=self.module.configuration.secret,
            scope="connect.api.read",
            stop_event=self._stop_event,
            log_cb=self.log,
        )

    @cached_property
    def metadata(self) -> Metadata:
        return Metadata(
            product=Product(name=self.PRODUCT_NAME, vendor_name=self.PRODUCT_VENDOR),
            version=self.OCSF_VERSION,
        )

    @staticmethod
    def _split(value: str | None) -> list[str]:
        return [item.strip() for item in (value or "").split(",") if item.strip()]

    @staticmethod
    def _normalize_mac(mac: str) -> str:
        return mac.replace("-", ":").upper()

    def _get_device_type(self, device: WithSecureDevice) -> tuple[DeviceTypeStr, DeviceTypeId]:
        if device.type == "mobile":
            return DeviceTypeStr.MOBILE, DeviceTypeId.MOBILE
        # the Elements Connector is a relay service installed on a server
        if device.type == "connector":
            return DeviceTypeStr.SERVER, DeviceTypeId.SERVER
        if device.type == "computer":
            variant = device.subscription.productVariant if device.subscription else None
            os_name = (device.os.name if device.os else None) or ""
            if variant in self.SERVER_PRODUCT_VARIANTS or "server" in os_name.lower():
                return DeviceTypeStr.SERVER, DeviceTypeId.SERVER
            return DeviceTypeStr.DESKTOP, DeviceTypeId.DESKTOP
        return DeviceTypeStr.UNKNOWN, DeviceTypeId.UNKNOWN

    def _get_os(self, device: WithSecureDevice) -> OperatingSystem | None:
        if not device.os or not device.os.name:
            return None

        name = f"{device.os.name} {device.os.version}" if device.os.version else device.os.name
        lowered = device.os.name.lower()
        os_type, os_type_id = next(
            ((type_str, type_id) for keyword, type_str, type_id in self.OS_KEYWORDS if keyword in lowered),
            (OSTypeStr.UNKNOWN, OSTypeId.UNKNOWN),
        )
        return OperatingSystem(name=name, type=os_type, type_id=os_type_id)

    def _get_ip_interfaces(self, device: WithSecureDevice) -> tuple[list[IPInterface], str | None]:
        """
        Parse the IPv4 (CIDR notation) and IPv6 addresses of the device.
        Returns the addresses and the subnet of the first IPv4 address given with a prefix.
        """
        interfaces: list[IPInterface] = []
        subnet: str | None = None
        for entry in self._split(device.ipAddresses) + self._split(device.ipv6Addresses):
            try:
                interface = ipaddress.ip_interface(entry)
            except ValueError:
                self.log(f"Device {device.id}: ignoring invalid IP address '{entry}'", level="debug")
                continue
            if subnet is None and interface.version == 4 and "/" in entry:
                subnet = str(interface.network)
            interfaces.append(interface)
        return interfaces, subnet

    def _get_network_interfaces(
        self, device: WithSecureDevice, ips: list[IPInterface]
    ) -> list[NetworkInterface] | None:
        # The API returns IP and MAC addresses as independent lists: they are paired by position.
        macs = [self._normalize_mac(mac) for mac in self._split(device.macAddresses)]
        network_interfaces = [
            NetworkInterface(
                hostname=device.name if index == 0 else None,
                ip=str(interface.ip),
                mac=macs[index] if index < len(macs) else None,
            )
            for index, interface in enumerate(ips)
        ]
        network_interfaces.extend(NetworkInterface(mac=mac) for mac in macs[len(ips) :])

        if device.publicIpAddress:
            network_interfaces.append(NetworkInterface(ip=device.publicIpAddress))

        return network_interfaces or None

    def _get_storage_encryption(self, device: WithSecureDevice) -> EncryptionObject | None:
        partitions: dict[str, Literal["Enabled", "Disabled"]] = {
            drive.drive: "Enabled" if drive.protectionStatus else "Disabled"
            for drive in device.encryptedDrives
            if drive.drive
        }
        if not partitions and device.discEncryptionEnabled is not None:
            partitions = {"system": "Enabled" if device.discEncryptionEnabled else "Disabled"}
        return EncryptionObject(partitions=partitions) if partitions else None

    def _get_enrichments(self, device: WithSecureDevice) -> list[DeviceEnrichmentObject] | None:
        users = list(dict.fromkeys(user for user in (device.lastUser, device.userPrincipalName, device.email) if user))
        data = DeviceDataObject(
            Firewall_status=self.FIREWALL_STATES.get(device.firewallState or ""),
            Storage_encryption=self._get_storage_encryption(device),
            Users=users or None,
            Full_qualified_domain_name=device.dnsAddress if device.dnsAddress and "." in device.dnsAddress else None,
        )
        if not data.model_dump(exclude_none=True):
            return None
        return [DeviceEnrichmentObject(name="compliance", value="hygiene", data=data)]

    def map_fields(self, device: WithSecureDevice) -> DeviceOCSFModel:
        device_type, device_type_id = self._get_device_type(device)
        ips, subnet = self._get_ip_interfaces(device)
        ipv4 = [interface for interface in ips if interface.version == 4]
        primary_ip = str((ipv4 or ips)[0].ip) if ips else None

        registration_time = device.registrationTimestamp.timestamp() if device.registrationTimestamp else None
        last_seen_time = device.statusUpdateTimestamp.timestamp() if device.statusUpdateTimestamp else None

        org = None
        if device.company and device.company.name:
            org = Organization(uid=device.company.id, name=device.company.name)

        groups = [Group(uid=group.id, name=group.name) for group in device.assetGroups if group.name]

        ocsf_device = Device(
            type=device_type,
            type_id=device_type_id,
            uid=device.id,
            hostname=device.name or device.dnsAddress or device.id,
            name=device.name,
            os=self._get_os(device),
            ip=primary_ip,
            subnet=subnet,
            network_interfaces=self._get_network_interfaces(device, ips),
            model=device.computerModel,
            uid_alt=device.serialNumber or None,
            created_time=registration_time,
            first_seen_time=registration_time,
            last_seen_time=last_seen_time,
            boot_time=device.lastRestartTime.timestamp() if device.lastRestartTime else None,
            org=org,
            groups=groups or None,
            is_managed=True,
            is_compliant=self.COMPLIANCE_STATES.get(device.protectionStatusOverview or ""),
            risk_score=device.vmRiskScore,
        )

        return DeviceOCSFModel(
            activity_id=self.ACTIVITY_ID,
            activity_name=self.ACTIVITY_NAME,
            category_name=self.CATEGORY_NAME,
            category_uid=self.CATEGORY_UID,
            class_name=self.CLASS_NAME,
            class_uid=self.CLASS_UID,
            type_name=self.TYPE_NAME,
            type_uid=self.TYPE_UID,
            severity="Informational",
            severity_id=1,
            time=last_seen_time or datetime.now(UTC).timestamp(),
            metadata=self.metadata,
            device=ocsf_device,
            enrichments=self._get_enrichments(device),
        )

    def _fetch_devices(self) -> Generator[WithSecureDevice]:
        """
        List the active devices, page by page. The API offers no incremental filter.
        """
        params: dict[str, str | int] = {"limit": API_LIST_DEVICES_PAGE_SIZE}
        headers = {"Accept": "application/json"}

        while self.running:
            response = self.client.get(API_LIST_DEVICES_URL, params=params, headers=headers, timeout=API_TIMEOUT)
            response.raise_for_status()
            payload = response.json()

            for item in payload.get("items", []):
                # the API may return empty objects
                if not item:
                    continue
                try:
                    yield WithSecureDevice.model_validate(item)
                except ValidationError as error:
                    self.log(f"Skipping invalid device {item.get('id')}: {error}", level="warning")

            next_anchor = payload.get("nextAnchor")
            if not next_anchor:
                return
            params["anchor"] = next_anchor

    def iterate_devices(self) -> Generator[WithSecureDevice]:
        """
        Yield the devices updated since the checkpoint.
        The new checkpoint is computed only once the whole listing is read: the listing is not
        ordered, so an intermediate checkpoint would skip the devices of the next pages.
        """
        checkpoint = datetime.fromisoformat(self.most_recent_date_seen) if self.most_recent_date_seen else None
        max_date = checkpoint

        for device in self._fetch_devices():
            updated_at = device.statusUpdateTimestamp
            if updated_at:
                if max_date is None or updated_at > max_date:
                    max_date = updated_at
                if checkpoint and updated_at <= checkpoint:
                    continue
            yield device

        if max_date and max_date != checkpoint:
            self._latest_time = max_date.isoformat()

    def get_mapped_fields(self) -> dict[str, str]:
        """Return the WithSecure -> OCSF field mapping, mirroring device_mapping.yml."""
        return {
            "id": "device.uid",
            "name": "device.hostname",
            "dnsAddress": "enrichments.data.Full_qualified_domain_name",
            "type": "device.type",
            "subscription.productVariant": "device.type",
            "os.name": "device.os",
            "os.version": "device.os.name",
            "ipAddresses": "device.ip",
            "ipv6Addresses": "device.network_interfaces.ip",
            "macAddresses": "device.network_interfaces.mac",
            "publicIpAddress": "device.network_interfaces",
            "computerModel": "device.model",
            "serialNumber": "device.uid_alt",
            "registrationTimestamp": "device.created_time",
            "statusUpdateTimestamp": "device.last_seen_time",
            "lastRestartTime": "device.boot_time",
            "company.id": "device.org.uid",
            "company.name": "device.org.name",
            "assetGroups": "device.groups",
            "protectionStatusOverview": "device.is_compliant",
            "vmRiskScore": "device.risk_score",
            "firewallState": "enrichments.data.Firewall_status",
            "encryptedDrives": "enrichments.data.Storage_encryption",
            "discEncryptionEnabled": "enrichments.data.Storage_encryption",
            "lastUser": "enrichments.data.Users",
            "userPrincipalName": "enrichments.data.Users",
            "email": "enrichments.data.Users",
        }

    def reset_checkpoint(self) -> None:
        with self.context as cache:
            cache.pop("most_recent_date_seen", None)
        self._latest_time = None
        self.log("Checkpoint reset - all devices will be collected on the next cycle", level="info")

    def update_checkpoint(self) -> None:
        if self._latest_time:
            with self.context as cache:
                cache["most_recent_date_seen"] = self._latest_time
            self.log(f"Checkpoint updated to {self._latest_time}", level="debug")

    def get_assets(self) -> Generator[DeviceOCSFModel]:
        self.log("Starting WithSecure device asset collection", level="info")
        self._latest_time = None
        total = 0

        try:
            for device in self.iterate_devices():
                try:
                    asset = self.map_fields(device)
                except ValidationError as error:
                    self.log(f"Skipping device {device.id}: {error}", level="warning")
                    continue
                total += 1
                yield asset
        except Exception as error:
            self.log(f"Failed to collect WithSecure devices: {human_readable_api_exception(error)}", level="error")
            raise

        self.log(f"WithSecure device asset collection complete - {total} devices", level="info")
