"""Shared helpers to map Holm Security records to OCSF objects.

Used by the device inventory connector and the vulnerability connector so timestamps
and device sub-objects are built consistently from Holm records.
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

from holm_security.asset_connector.models import HolmNetwork

# Holm os_family -> (OCSF OSTypeStr, OCSF OSTypeId)
OS_FAMILY_MAP: dict[str, tuple[OSTypeStr, OSTypeId]] = {
    "windows": (OSTypeStr.WINDOWS, OSTypeId.WINDOWS),
    "linux": (OSTypeStr.LINUX, OSTypeId.LINUX),
    "macos": (OSTypeStr.MACOS, OSTypeId.MACOS),
    "mac": (OSTypeStr.MACOS, OSTypeId.MACOS),
    "android": (OSTypeStr.ANDROID, OSTypeId.ANDROID),
    "ios": (OSTypeStr.IOS, OSTypeId.IOS),
}


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


def build_operating_system(os_name: str | None, os_family: str | None) -> OperatingSystem | None:
    """Map the Holm device agent OS fields to an OCSF ``OperatingSystem`` object."""
    if os_name is None and os_family is None:
        return None

    os_type: OSTypeStr = OSTypeStr.UNKNOWN
    os_type_id: OSTypeId = OSTypeId.UNKNOWN
    if os_family:
        os_type, os_type_id = OS_FAMILY_MAP.get(os_family.strip().lower(), (OSTypeStr.OTHER, OSTypeId.OTHER))

    return OperatingSystem(name=os_name, type=os_type, type_id=os_type_id)


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
