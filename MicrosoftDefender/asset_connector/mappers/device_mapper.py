from datetime import datetime

from dateutil.parser import isoparse
from msgraph.generated.models.managed_device import ManagedDevice
from sekoia_automation.asset_connector.models.ocsf.device import (
    Device,
    DeviceEnrichmentObject,
    DeviceTypeId,
    DeviceTypeStr,
    Group,
    NetworkInterface,
    NetworkInterfaceTypeId,
    NetworkInterfaceTypeStr,
    OperatingSystem,
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.asset_connector.models.ocsf.risk_level import RiskLevelId, RiskLevelStr

from asset_connector.models import DefenderMachine

# The platform rejects an asset whose name is shorter than this (and the whole push batch with it)
MIN_HOSTNAME_LENGTH = 2

# Mapping from Defender osPlatform string to OCSF OS type
OS_TYPE_MAP: dict[str, tuple[OSTypeStr, OSTypeId]] = {
    "windows": (OSTypeStr.WINDOWS, OSTypeId.WINDOWS),
    "linux": (OSTypeStr.LINUX, OSTypeId.LINUX),
    "macos": (OSTypeStr.MACOS, OSTypeId.MACOS),
    "android": (OSTypeStr.ANDROID, OSTypeId.ANDROID),
    "ios": (OSTypeStr.IOS, OSTypeId.IOS),
    "ipados": (OSTypeStr.IPADOS, OSTypeId.IPADOS),
}

# Mapping from Defender riskScore to OCSF risk level
RISK_LEVEL_MAP: dict[str, tuple[RiskLevelStr, RiskLevelId]] = {
    "informational": (RiskLevelStr.INFO, RiskLevelId.INFO),
    "low": (RiskLevelStr.LOW, RiskLevelId.LOW),
    "medium": (RiskLevelStr.MEDIUM, RiskLevelId.MEDIUM),
    "high": (RiskLevelStr.HIGH, RiskLevelId.HIGH),
    "critical": (RiskLevelStr.CRITICAL, RiskLevelId.CRITICAL),
}

# Mapping from Defender interface type string to OCSF network interface type
NETWORK_INTERFACE_TYPE_MAP: dict[str, tuple[NetworkInterfaceTypeStr, NetworkInterfaceTypeId]] = {
    "ethernet": (NetworkInterfaceTypeStr.WIRED, NetworkInterfaceTypeId.WIRED),
    "wifi": (NetworkInterfaceTypeStr.WIRELESS, NetworkInterfaceTypeId.WIRELESS),
}


class MissingHostnameError(ValueError):
    """Raised when a device has no name usable as an asset hostname."""


class DeviceMapper:
    """Map a Defender machine, enriched with its Intune managed device, to OCSF device objects."""

    def __init__(self, machine: DefenderMachine, managed_device: ManagedDevice | None = None) -> None:
        self.machine = machine
        self.managed_device = managed_device

    # Value resolvers

    @staticmethod
    def resolve_hostname(computer_dns_name: str | None) -> tuple[str | None, str | None]:
        """Split a Defender computerDnsName into its short hostname and its domain.

        The hostname is None when the first label is shorter than MIN_HOSTNAME_LENGTH.
        """
        if not computer_dns_name:
            return None, None
        short_name, _, domain = computer_dns_name.strip().partition(".")
        hostname = short_name if len(short_name) >= MIN_HOSTNAME_LENGTH else None
        return hostname, domain or None

    @staticmethod
    def resolve_os_type(os_platform: str | None) -> tuple[OSTypeStr, OSTypeId]:
        if not os_platform:
            return OSTypeStr.UNKNOWN, OSTypeId.UNKNOWN
        normalized = os_platform.strip().lower()
        for key, value in OS_TYPE_MAP.items():
            if key in normalized:
                return value
        return OSTypeStr.OTHER, OSTypeId.OTHER

    @staticmethod
    def resolve_device_type(os_str: OSTypeStr) -> tuple[DeviceTypeStr, DeviceTypeId]:
        if os_str in (OSTypeStr.ANDROID, OSTypeStr.IOS, OSTypeStr.IPADOS):
            return DeviceTypeStr.MOBILE, DeviceTypeId.MOBILE
        return DeviceTypeStr.DESKTOP, DeviceTypeId.DESKTOP

    @staticmethod
    def resolve_risk_level(risk_score: str | None) -> tuple[RiskLevelStr | None, RiskLevelId | None]:
        if not risk_score:
            return None, None
        normalized = risk_score.strip().lower()
        if normalized in RISK_LEVEL_MAP:
            return RISK_LEVEL_MAP[normalized]
        return RiskLevelStr.OTHER, RiskLevelId.OTHER

    @staticmethod
    def to_epoch(value: str | None) -> float | None:
        return isoparse(value).timestamp() if value else None

    # Device parts

    def build_hostname(self) -> tuple[str, str | None]:
        """Return the hostname and domain, falling back on the Intune device name.

        Raises MissingHostnameError when the machine has no usable name.
        """
        hostname, domain = self.resolve_hostname(self.machine.computerDnsName)
        if hostname is None and self.managed_device and self.managed_device.device_name:
            # Fall back on the Intune device name, keeping the domain from Defender
            hostname, _ = self.resolve_hostname(self.managed_device.device_name)
        if hostname is None:
            raise MissingHostnameError(
                f"machine {self.machine.id} has no usable hostname "
                f"(computerDnsName={self.machine.computerDnsName!r})"
            )
        return hostname, domain

    def build_device_type(self) -> tuple[DeviceTypeStr, DeviceTypeId]:
        os_type_str, _ = self.resolve_os_type(self.machine.osPlatform)
        return self.resolve_device_type(os_type_str)

    def build_os(self) -> OperatingSystem:
        os_type_str, os_type_id = self.resolve_os_type(self.machine.osPlatform)
        return OperatingSystem(name=self.build_os_name(), type=os_type_str, type_id=os_type_id)

    def build_os_name(self) -> str:
        # The Intune OS version is richer than the Defender platform and build
        if self.managed_device and self.managed_device.os_version:
            return self.managed_device.os_version
        os_name = self.machine.osPlatform or ""
        if self.machine.osBuild:
            os_name = f"{os_name} (Build {self.machine.osBuild})"
        return os_name

    def build_groups(self) -> list[Group] | None:
        if not self.machine.rbacGroupName:
            return None
        rbac_group_id = self.machine.rbacGroupId
        return [Group(name=self.machine.rbacGroupName, uid=str(rbac_group_id) if rbac_group_id is not None else None)]

    def build_network_interfaces(self) -> list[NetworkInterface] | None:
        # Intune MAC addresses first, then the Defender IP addresses
        return self.build_managed_network_interfaces() or self.build_defender_network_interfaces()

    def build_managed_network_interfaces(self) -> list[NetworkInterface] | None:
        if not self.managed_device:
            return None
        interfaces = []
        if self.managed_device.ethernet_mac_address:
            interfaces.append(
                NetworkInterface(
                    mac=self.managed_device.ethernet_mac_address,
                    name="ethernet",
                    type=NetworkInterfaceTypeStr.WIRED,
                    type_id=NetworkInterfaceTypeId.WIRED,
                )
            )
        if self.managed_device.wi_fi_mac_address:
            interfaces.append(
                NetworkInterface(
                    mac=self.managed_device.wi_fi_mac_address,
                    name="wifi",
                    type=NetworkInterfaceTypeStr.WIRELESS,
                    type_id=NetworkInterfaceTypeId.WIRELESS,
                )
            )
        return interfaces or None

    def build_defender_network_interfaces(self) -> list[NetworkInterface] | None:
        interfaces = []
        for iface in self.machine.ipAddresses or []:
            mac = iface.get("macAddress")
            ip_addr = iface.get("ipAddress")
            if not (mac or ip_addr):
                continue
            iface_type = (iface.get("type") or "").lower()
            type_str, type_id = NETWORK_INTERFACE_TYPE_MAP.get(
                iface_type, (NetworkInterfaceTypeStr.OTHER, NetworkInterfaceTypeId.OTHER)
            )
            interfaces.append(
                NetworkInterface(mac=mac, ip=ip_addr, name=iface_type or None, type=type_str, type_id=type_id)
            )
        return interfaces or None

    def build_is_compliant(self) -> bool | None:
        if not (self.managed_device and self.managed_device.compliance_state):
            return None
        return self.managed_device.compliance_state.value == "compliant"

    def build_is_personal(self) -> bool | None:
        if not (self.managed_device and self.managed_device.managed_device_owner_type):
            return None
        return self.managed_device.managed_device_owner_type.value == "personal"

    def build_event_time(self) -> float:
        return (
            self.to_epoch(self.machine.lastSeen) or self.to_epoch(self.machine.firstSeen) or datetime.now().timestamp()
        )

    # OCSF objects

    def build_device(self) -> Device:
        """Build the full OCSF Device. Raises MissingHostnameError when the machine has no usable name."""
        hostname, domain = self.build_hostname()
        device_type_str, device_type_id = self.build_device_type()
        risk_level_str, risk_level_id = self.resolve_risk_level(self.machine.riskScore)
        managed_device = self.managed_device

        return Device(
            type_id=device_type_id,
            type=device_type_str,
            uid=self.machine.id,
            uid_alt=self.machine.aadDeviceId,
            hostname=hostname,
            domain=domain,
            ip=self.machine.lastIpAddress,
            os=self.build_os(),
            model=managed_device.model if managed_device else None,
            vendor_name=managed_device.manufacturer if managed_device else None,
            first_seen_time=self.to_epoch(self.machine.firstSeen),
            last_seen_time=self.to_epoch(self.machine.lastSeen),
            imei_list=[managed_device.imei] if managed_device and managed_device.imei else None,
            meid=managed_device.meid if managed_device else None,
            iccid=managed_device.iccid if managed_device else None,
            udid=managed_device.udid if managed_device else None,
            groups=self.build_groups(),
            network_interfaces=self.build_network_interfaces(),
            is_compliant=self.build_is_compliant(),
            is_managed=True,
            is_personal=self.build_is_personal(),
            is_supervised=managed_device.is_supervised if managed_device else None,
            risk_level=risk_level_str,
            risk_level_id=risk_level_id,
        )

    def build_minimal_device(self) -> Device:
        """Build an OCSF Device with only its type, uid and hostname, to reference it from another asset.

        Raises MissingHostnameError when the machine has no usable name.
        """
        hostname, _ = self.build_hostname()
        device_type_str, device_type_id = self.build_device_type()
        return Device(type_id=device_type_id, type=device_type_str, uid=self.machine.id, hostname=hostname)

    def build_enrichments(self) -> list[DeviceEnrichmentObject] | None:
        enrichments = []
        if self.machine.aadDeviceId:
            enrichments.append(DeviceEnrichmentObject(name="azure_ad_device_id", value=self.machine.aadDeviceId))
        if self.machine.healthStatus:
            enrichments.append(DeviceEnrichmentObject(name="health_status", value=self.machine.healthStatus))
        if self.machine.exposureLevel:
            enrichments.append(DeviceEnrichmentObject(name="exposure_level", value=self.machine.exposureLevel))
        if self.machine.rbacGroupName:
            enrichments.append(DeviceEnrichmentObject(name="rbac_group_name", value=self.machine.rbacGroupName))

        if self.managed_device:
            if self.managed_device.user_principal_name:
                enrichments.append(
                    DeviceEnrichmentObject(name="user_principal_name", value=self.managed_device.user_principal_name)
                )
            if self.managed_device.management_agent:
                enrichments.append(
                    DeviceEnrichmentObject(name="management_agent", value=self.managed_device.management_agent.value)
                )

        return enrichments or None
