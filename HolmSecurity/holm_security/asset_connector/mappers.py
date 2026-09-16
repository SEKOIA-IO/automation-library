"""Shared helpers to map Holm Security records to OCSF objects.

Used by the device inventory connector and the vulnerability connector so device
sub-objects are built consistently from Holm device agents and network assets.
"""

from datetime import datetime

from dateutil.parser import isoparse
from sekoia_automation.asset_connector.models.ocsf.device import (
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

from holm_security.asset_connector.models import HolmNetwork, HolmSeverityBreakdown

# Holm os_family -> (OCSF OSTypeStr, OCSF OSTypeId)
OS_FAMILY_MAP: dict[str, tuple[OSTypeStr, OSTypeId]] = {
    "windows": (OSTypeStr.WINDOWS, OSTypeId.WINDOWS),
    "linux": (OSTypeStr.LINUX, OSTypeId.LINUX),
    "macos": (OSTypeStr.MACOS, OSTypeId.MACOS),
    "mac": (OSTypeStr.MACOS, OSTypeId.MACOS),
    "android": (OSTypeStr.ANDROID, OSTypeId.ANDROID),
    "ios": (OSTypeStr.IOS, OSTypeId.IOS),
}

# Keywords found in the free-form ``operating_system`` field of a network asset.
# Ordered: the first keyword contained in the lowercased value wins.
OS_NAME_KEYWORDS: list[tuple[str, tuple[OSTypeStr, OSTypeId]]] = [
    ("windows", (OSTypeStr.WINDOWS, OSTypeId.WINDOWS)),
    ("android", (OSTypeStr.ANDROID, OSTypeId.ANDROID)),
    ("ipados", (OSTypeStr.IPADOS, OSTypeId.IPADOS)),
    ("ios", (OSTypeStr.IOS, OSTypeId.IOS)),
    ("macos", (OSTypeStr.MACOS, OSTypeId.MACOS)),
    ("mac os", (OSTypeStr.MACOS, OSTypeId.MACOS)),
    ("darwin", (OSTypeStr.MACOS, OSTypeId.MACOS)),
    ("solaris", (OSTypeStr.SOLARIS, OSTypeId.SOLARIS)),
    ("aix", (OSTypeStr.AIX, OSTypeId.AIX)),
    ("hp-ux", (OSTypeStr.HPUX, OSTypeId.HPUX)),
    ("ubuntu", (OSTypeStr.LINUX, OSTypeId.LINUX)),
    ("debian", (OSTypeStr.LINUX, OSTypeId.LINUX)),
    ("centos", (OSTypeStr.LINUX, OSTypeId.LINUX)),
    ("red hat", (OSTypeStr.LINUX, OSTypeId.LINUX)),
    ("redhat", (OSTypeStr.LINUX, OSTypeId.LINUX)),
    ("rhel", (OSTypeStr.LINUX, OSTypeId.LINUX)),
    ("fedora", (OSTypeStr.LINUX, OSTypeId.LINUX)),
    ("suse", (OSTypeStr.LINUX, OSTypeId.LINUX)),
    ("alpine", (OSTypeStr.LINUX, OSTypeId.LINUX)),
    ("linux", (OSTypeStr.LINUX, OSTypeId.LINUX)),
]

# Holm network asset ``type`` -> (OCSF DeviceTypeStr, OCSF DeviceTypeId).
# Holm exposes no server/desktop signal for scanned assets, so a single host
# stays Unknown rather than being guessed, and an IP range maps to Other.
NET_ASSET_TYPE_MAP: dict[str, tuple[DeviceTypeStr, DeviceTypeId]] = {
    "host": (DeviceTypeStr.UNKNOWN, DeviceTypeId.UNKNOWN),
    "network": (DeviceTypeStr.OTHER, DeviceTypeId.OTHER),
}

# Severity buckets of a Holm severity breakdown, from the most to the least severe.
SEVERITY_BREAKDOWN_RISK: list[tuple[str, tuple[RiskLevelStr, RiskLevelId]]] = [
    ("critical", (RiskLevelStr.CRITICAL, RiskLevelId.CRITICAL)),
    ("high", (RiskLevelStr.HIGH, RiskLevelId.HIGH)),
    ("medium", (RiskLevelStr.MEDIUM, RiskLevelId.MEDIUM)),
    ("low", (RiskLevelStr.LOW, RiskLevelId.LOW)),
    ("info", (RiskLevelStr.INFO, RiskLevelId.INFO)),
]


def parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp, returning ``None`` when it is absent or malformed.

    Holm timestamps are not validated by the API, so a single malformed value must
    never abort a whole collection cycle.
    """
    if not value:
        return None

    try:
        return isoparse(value)
    except (ValueError, OverflowError, TypeError):
        return None


def to_epoch(value: str | None) -> float | None:
    """Convert an ISO 8601 timestamp to a Unix epoch float."""
    parsed = parse_datetime(value)
    return parsed.timestamp() if parsed is not None else None


def to_int_epoch(value: str | None) -> int | None:
    """Convert an ISO 8601 timestamp to a Unix epoch integer."""
    epoch = to_epoch(value)
    return int(epoch) if epoch is not None else None


def map_device_type(os_is_server: bool | None) -> tuple[DeviceTypeStr, DeviceTypeId]:
    """Map ``os_is_server`` to an OCSF device type."""
    if os_is_server:
        return DeviceTypeStr.SERVER, DeviceTypeId.SERVER
    if os_is_server is False:
        return DeviceTypeStr.DESKTOP, DeviceTypeId.DESKTOP
    return DeviceTypeStr.UNKNOWN, DeviceTypeId.UNKNOWN


def map_net_asset_type(asset_type: str | None) -> tuple[DeviceTypeStr, DeviceTypeId]:
    """Map the Holm network asset ``type`` to an OCSF device type."""
    if not asset_type:
        return DeviceTypeStr.UNKNOWN, DeviceTypeId.UNKNOWN
    return NET_ASSET_TYPE_MAP.get(asset_type.strip().lower(), (DeviceTypeStr.OTHER, DeviceTypeId.OTHER))


def build_operating_system(os_name: str | None, os_family: str | None) -> OperatingSystem | None:
    """Map the Holm device agent OS fields to an OCSF ``OperatingSystem`` object."""
    if os_name is None and os_family is None:
        return None

    os_type: OSTypeStr = OSTypeStr.UNKNOWN
    os_type_id: OSTypeId = OSTypeId.UNKNOWN
    if os_family:
        os_type, os_type_id = OS_FAMILY_MAP.get(os_family.strip().lower(), (OSTypeStr.OTHER, OSTypeId.OTHER))

    return OperatingSystem(name=os_name, type=os_type, type_id=os_type_id)


def build_operating_system_from_name(operating_system: str | None) -> OperatingSystem | None:
    """Map the free-form ``operating_system`` of a network asset to an OCSF object.

    Holm reports scanned assets with a display string such as ``Ubuntu 16.04`` or
    ``Debian GNU/Linux 12``, so the OS type is derived from known keywords.
    """
    if not operating_system:
        return None

    lowered = operating_system.strip().lower()
    for keyword, (os_type, os_type_id) in OS_NAME_KEYWORDS:
        if keyword in lowered:
            return OperatingSystem(name=operating_system, type=os_type, type_id=os_type_id)

    return OperatingSystem(name=operating_system, type=OSTypeStr.OTHER, type_id=OSTypeId.OTHER)


def map_severity_breakdown(
    severity: HolmSeverityBreakdown | None,
) -> tuple[RiskLevelStr | None, RiskLevelId | None]:
    """Derive an OCSF risk level from the most severe non-empty bucket of a breakdown."""
    if severity is None:
        return None, None

    for bucket, risk_level in SEVERITY_BREAKDOWN_RISK:
        if getattr(severity, bucket, 0):
            return risk_level

    return None, None


def build_network_interfaces(network: HolmNetwork | None, hostname: str | None) -> list[NetworkInterface] | None:
    """Build the primary IPv4 and secondary IPv6 network interfaces from a Holm network block."""
    if network is None:
        return None

    interfaces: list[NetworkInterface] = []

    if network.ip_address:
        interfaces.append(
            NetworkInterface(
                ip=network.ip_address,
                mac=network.mac_address,
                hostname=hostname,
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
