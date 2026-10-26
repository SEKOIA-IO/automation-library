from sekoia_automation.asset_connector.models.ocsf.device import (
    Device,
    DeviceTypeId,
    DeviceTypeStr,
    GeoLocation,
    NetworkInterface,
    NetworkInterfaceTypeId,
    NetworkInterfaceTypeStr,
    OperatingSystem,
    OSTypeId,
    OSTypeStr,
)

from tenable_conn.asset_connector.helpers import parse_datetime_to_timestamp
from tenable_conn.asset_connector.models.assets_export_model import (
    AssetExportV2,
    AssetNetwork,
    AssetTimestamps,
    NetworkInterfaceV2 as TenableNetworkInterface,
)


class TenableDeviceMapper:
    """
    Map one Tenable asset (Export Assets v2 shape) to the OCSF Device object.

    One instance per asset: it is built with the asset and `map()` produces the OCSF object. The class-level
    helpers (`map_os_type`, `map_device_type`, `build_network_interfaces`) do not depend on the asset.
    """

    UNKNOWN_HOSTNAME: str = "unknown"

    def __init__(self, asset_info: AssetExportV2) -> None:
        self.asset_info = asset_info

    @property
    def network(self) -> AssetNetwork | None:
        return self.asset_info.network

    @property
    def timestamps(self) -> AssetTimestamps | None:
        return self.asset_info.timestamps

    @property
    def first_hostname(self) -> str | None:
        return self.network.hostnames[0] if self.network and self.network.hostnames else None

    @property
    def first_fqdn(self) -> str | None:
        return self.network.fqdns[0] if self.network and self.network.fqdns else None

    @property
    def first_ipv4(self) -> str | None:
        return self.network.ipv4s[0] if self.network and self.network.ipv4s else None

    @property
    def hostname(self) -> str:
        """Same fallback chain for exported and fallback-fetched assets: hostname, name, FQDN, "unknown"."""
        return self.first_hostname or self.asset_info.name or self.first_fqdn or self.UNKNOWN_HOSTNAME

    @property
    def display_name(self) -> str | None:
        """The device name: asset name, then hostname, then FQDN."""
        return self.asset_info.name or self.first_hostname or self.first_fqdn

    def map(self) -> Device:
        """
        Map the asset to the OCSF Device object.
        :return: A Device object.
        """
        device_type_str, device_type_id = self.map_device_type(
            self.asset_info.system_types[0] if self.asset_info.system_types else None
        )

        return Device(
            uid=self.asset_info.id,
            type=device_type_str,
            type_id=device_type_id,
            hostname=self.hostname,
            name=self.display_name,
            os=self.build_operating_system(),
            location=self.build_location(),
            ip=self.first_ipv4,
            network_interfaces=self.build_asset_network_interfaces(),
            first_seen_time=parse_datetime_to_timestamp(self.timestamps.first_seen if self.timestamps else None),
            last_seen_time=parse_datetime_to_timestamp(self.timestamps.last_seen if self.timestamps else None),
            created_time=parse_datetime_to_timestamp(self.timestamps.created_at if self.timestamps else None),
            is_managed=self.asset_info.has_agent or False,
        )

    def build_operating_system(self) -> OperatingSystem | None:
        """
        Build the OperatingSystem from the first operating system reported by Tenable.
        :return: An OperatingSystem object, or None when the asset has no operating system.
        """
        os_list = self.asset_info.operating_systems
        if not os_list:
            return None
        os_type_str, os_type_id = self.map_os_type(os_list[0])
        return OperatingSystem(name=os_list[0], type=os_type_str, type_id=os_type_id)

    def build_location(self) -> GeoLocation | None:
        """
        Build the GeoLocation from the cloud region (AWS region, Azure location or GCP zone).
        :return: A GeoLocation object, or None for a non-cloud asset.
        """
        cloud = self.asset_info.cloud
        aws_region = cloud.aws.region if cloud and cloud.aws else None
        azure_location = cloud.azure.location if cloud and cloud.azure else None
        gcp_zone = cloud.gcp.zone if cloud and cloud.gcp else None
        location_str = aws_region or azure_location or gcp_zone
        return GeoLocation(country=None, city=location_str) if location_str else None

    def build_asset_network_interfaces(self) -> list[NetworkInterface] | None:
        """
        Build the NetworkInterface list of the asset.
        :return: The list of NetworkInterface objects, or None when the asset reports no interface.
        """
        interfaces = self.network.network_interfaces if self.network else []
        return self.build_network_interfaces(interfaces) if interfaces else None

    @classmethod
    def build_network_interfaces(cls, interfaces_data: list[TenableNetworkInterface]) -> list[NetworkInterface]:
        """
        Build a list of NetworkInterface objects from the interfaces data.
        :param interfaces_data: A list of TenableNetworkInterface model objects.
        :return: A list of NetworkInterface objects.
        """
        network_interfaces = []
        for iface in interfaces_data or []:
            interface = cls.build_network_interface(iface)
            if interface is not None:
                network_interfaces.append(interface)
        return network_interfaces

    @classmethod
    def build_network_interface(cls, iface: TenableNetworkInterface) -> NetworkInterface | None:
        """
        Build one NetworkInterface from a Tenable interface.
        :param iface: The TenableNetworkInterface model object.
        :return: A NetworkInterface object, or None when the interface carries no name, FQDN, IPv4 or MAC.
        """
        raw_name = iface.name or ""
        ipv4_list = iface.ipv4s
        mac_list = iface.mac_addresses
        fqdn_list = iface.fqdns

        if not (fqdn_list or ipv4_list or mac_list or raw_name):
            return None

        interface_type, interface_type_id = cls.map_interface_type(iface)
        return NetworkInterface(
            hostname=fqdn_list[0] if fqdn_list else None,
            ip=ipv4_list[0] if ipv4_list else None,
            mac=mac_list[0] if mac_list else None,
            name=raw_name,
            type=interface_type,
            type_id=interface_type_id,
        )

    @staticmethod
    def map_interface_type(iface: TenableNetworkInterface) -> tuple[NetworkInterfaceTypeStr, NetworkInterfaceTypeId]:
        """
        Map a Tenable interface to the OCSF interface type, from its virtual flag and its name.
        :param iface: The TenableNetworkInterface model object.
        :return: A tuple containing NetworkInterfaceTypeStr and NetworkInterfaceTypeId.
        """
        wireless_keywords = ["wireless", "wi-fi", "wifi", "wlan", "802.11"]
        mobile_keywords = ["mobile", "cellular", "wwan", "4g", "5g", "lte"]
        tunnel_keywords = ["tun", "tap", "docker", "vpn", "virtual", "cni"]

        raw_name = iface.name or ""
        name_lower = raw_name.lower()

        if iface.virtual is True or any(k in name_lower for k in tunnel_keywords):
            return NetworkInterfaceTypeStr.TUNNEL, NetworkInterfaceTypeId.TUNNEL
        if any(k in name_lower for k in mobile_keywords):
            return NetworkInterfaceTypeStr.MOBILE, NetworkInterfaceTypeId.MOBILE
        if any(k in name_lower for k in wireless_keywords):
            return NetworkInterfaceTypeStr.WIRELESS, NetworkInterfaceTypeId.WIRELESS
        if raw_name and "catch_all" not in name_lower:
            return NetworkInterfaceTypeStr.WIRED, NetworkInterfaceTypeId.WIRED
        return NetworkInterfaceTypeStr.UNKNOWN, NetworkInterfaceTypeId.UNKNOWN

    @staticmethod
    def map_os_type(os_name: str | None) -> tuple[OSTypeStr, OSTypeId]:
        """
        Map operating system name to OSTypeStr and OSTypeId.
        :param os_name: The operating system name.
        :return: A tuple containing OSTypeStr and OSTypeId.
        """
        if not os_name:
            return OSTypeStr.UNKNOWN, OSTypeId.UNKNOWN

        os_lower = os_name.lower()

        os_mappings = [
            (["windows mobile"], (OSTypeStr.WINDOWS_MOBILE, OSTypeId.WINDOWS_MOBILE)),
            (["windows"], (OSTypeStr.WINDOWS, OSTypeId.WINDOWS)),
            (["linux", "centos", "ubuntu", "debian", "red hat", "rhel"], (OSTypeStr.LINUX, OSTypeId.LINUX)),
            (["android"], (OSTypeStr.ANDROID, OSTypeId.ANDROID)),
            (["macos", "mac os"], (OSTypeStr.MACOS, OSTypeId.MACOS)),
            (["ios"], (OSTypeStr.IOS, OSTypeId.IOS)),
            (["ipados"], (OSTypeStr.IPADOS, OSTypeId.IPADOS)),
            (["solaris"], (OSTypeStr.SOLARIS, OSTypeId.SOLARIS)),
            (["aix"], (OSTypeStr.AIX, OSTypeId.AIX)),
            (["hp-ux", "hpux"], (OSTypeStr.HPUX, OSTypeId.HPUX)),
        ]

        for keywords, os_type in os_mappings:
            if any(keyword in os_lower for keyword in keywords):
                return os_type

        return OSTypeStr.OTHER, OSTypeId.OTHER

    @staticmethod
    def map_device_type(system_type: str | None) -> tuple[DeviceTypeStr, DeviceTypeId]:
        """
        Map system type to DeviceTypeStr and DeviceTypeId.
        :param system_type: The system type string.
        :return: A tuple containing DeviceTypeStr and DeviceTypeId.
        """
        if not system_type:
            return DeviceTypeStr.UNKNOWN, DeviceTypeId.UNKNOWN

        type_lower = system_type.lower()

        type_mappings = [
            (["server", "general-purpose"], (DeviceTypeStr.SERVER, DeviceTypeId.SERVER)),
            (["desktop", "laptop"], (DeviceTypeStr.DESKTOP, DeviceTypeId.DESKTOP)),
            (["mobile", "tablet", "iot"], (DeviceTypeStr.MOBILE, DeviceTypeId.MOBILE)),
            (["virtual", "vm"], (DeviceTypeStr.VIRTUAL, DeviceTypeId.VIRTUAL)),
            (["firewall"], (DeviceTypeStr.FIREWALL, DeviceTypeId.FIREWALL)),
            (["switch", "router"], (DeviceTypeStr.SWITCH, DeviceTypeId.SWITCH)),
        ]

        for keywords, device_type in type_mappings:
            if any(keyword in type_lower for keyword in keywords):
                return device_type

        return DeviceTypeStr.OTHER, DeviceTypeId.OTHER
