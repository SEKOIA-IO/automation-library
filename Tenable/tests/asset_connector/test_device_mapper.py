import pytest
from sekoia_automation.asset_connector.models.ocsf.device import (
    DeviceTypeId,
    DeviceTypeStr,
    NetworkInterfaceTypeId,
    NetworkInterfaceTypeStr,
    OSTypeId,
    OSTypeStr,
)

from tenable_conn.asset_connector.helpers import asset_details_to_export
from tenable_conn.asset_connector.mapper import TenableDeviceMapper
from tenable_conn.asset_connector.models.asset_details_model import AssetDetails
from tenable_conn.asset_connector.models.assets_export_model import (
    AssetExportV2 as AssetInfo,
    NetworkInterfaceV2 as TenableNetworkInterface,
)


def test_map_os_type_windows():
    os_type_str, os_type_id = TenableDeviceMapper.map_os_type("Windows 10 Pro")
    assert os_type_str == OSTypeStr.WINDOWS
    assert os_type_id == OSTypeId.WINDOWS


def test_map_os_type_linux():
    os_type_str, os_type_id = TenableDeviceMapper.map_os_type("CentOS Linux release 7.9")
    assert os_type_str == OSTypeStr.LINUX
    assert os_type_id == OSTypeId.LINUX


def test_map_os_type_android():
    os_type_str, os_type_id = TenableDeviceMapper.map_os_type("Android 12")
    assert os_type_str == OSTypeStr.ANDROID
    assert os_type_id == OSTypeId.ANDROID


def test_map_os_type_macos():
    os_type_str, os_type_id = TenableDeviceMapper.map_os_type("macOS Ventura")
    assert os_type_str == OSTypeStr.MACOS
    assert os_type_id == OSTypeId.MACOS


def test_map_os_type_ios():
    os_type_str, os_type_id = TenableDeviceMapper.map_os_type("iOS 16.5")
    assert os_type_str == OSTypeStr.IOS
    assert os_type_id == OSTypeId.IOS


def test_map_os_type_solaris():
    os_type_str, os_type_id = TenableDeviceMapper.map_os_type("Solaris 10 (sparc)")
    assert os_type_str == OSTypeStr.SOLARIS
    assert os_type_id == OSTypeId.SOLARIS


def test_map_os_type_aix():
    os_type_str, os_type_id = TenableDeviceMapper.map_os_type("AIX 7.2")
    assert os_type_str == OSTypeStr.AIX
    assert os_type_id == OSTypeId.AIX


def test_map_os_type_hpux():
    os_type_str, os_type_id = TenableDeviceMapper.map_os_type("HP-UX 11i v3")
    assert os_type_str == OSTypeStr.HPUX
    assert os_type_id == OSTypeId.HPUX


def test_map_os_type_unknown():
    os_type_str, os_type_id = TenableDeviceMapper.map_os_type(None)
    assert os_type_str == OSTypeStr.UNKNOWN
    assert os_type_id == OSTypeId.UNKNOWN


def test_map_os_type_other():
    os_type_str, os_type_id = TenableDeviceMapper.map_os_type("FreeBSD 13.1")
    assert os_type_str == OSTypeStr.OTHER
    assert os_type_id == OSTypeId.OTHER


def test_map_device_type_server():
    device_type_str, device_type_id = TenableDeviceMapper.map_device_type("general-purpose")
    assert device_type_str == DeviceTypeStr.SERVER
    assert device_type_id == DeviceTypeId.SERVER


def test_map_device_type_desktop():
    device_type_str, device_type_id = TenableDeviceMapper.map_device_type("desktop")
    assert device_type_str == DeviceTypeStr.DESKTOP
    assert device_type_id == DeviceTypeId.DESKTOP


def test_map_device_type_laptop():
    device_type_str, device_type_id = TenableDeviceMapper.map_device_type("laptop")
    assert device_type_str == DeviceTypeStr.DESKTOP
    assert device_type_id == DeviceTypeId.DESKTOP


def test_map_device_type_router():
    device_type_str, device_type_id = TenableDeviceMapper.map_device_type("router")
    assert device_type_str == DeviceTypeStr.SWITCH
    assert device_type_id == DeviceTypeId.SWITCH


def test_map_device_type_firewall():
    device_type_str, device_type_id = TenableDeviceMapper.map_device_type("firewall")
    assert device_type_str == DeviceTypeStr.FIREWALL
    assert device_type_id == DeviceTypeId.FIREWALL


def test_map_device_type_unknown():
    device_type_str, device_type_id = TenableDeviceMapper.map_device_type(None)
    assert device_type_str == DeviceTypeStr.UNKNOWN
    assert device_type_id == DeviceTypeId.UNKNOWN


def test_build_network_interfaces_wired():
    interfaces_data = [
        TenableNetworkInterface(
            name="eth0",
            ipv4s=["192.168.1.10"],
            ipv6s=[],
            mac_addresses=["00:11:22:33:44:55"],
            fqdns=["host.example.com"],
            virtual=False,
        )
    ]

    interfaces = TenableDeviceMapper.build_network_interfaces(interfaces_data)

    assert len(interfaces) == 1
    assert interfaces[0].type == NetworkInterfaceTypeStr.WIRED
    assert interfaces[0].type_id == NetworkInterfaceTypeId.WIRED
    assert interfaces[0].ip == "192.168.1.10"
    assert interfaces[0].mac == "00:11:22:33:44:55"


def test_build_network_interfaces_wireless():
    interfaces_data = [TenableNetworkInterface(name="wlan0", virtual=False)]
    interfaces = TenableDeviceMapper.build_network_interfaces(interfaces_data)

    assert len(interfaces) == 1
    assert interfaces[0].type == NetworkInterfaceTypeStr.WIRELESS
    assert interfaces[0].type_id == NetworkInterfaceTypeId.WIRELESS


def test_build_network_interfaces_tunnel():
    interfaces_data = [TenableNetworkInterface(name="tun0", virtual=True)]
    interfaces = TenableDeviceMapper.build_network_interfaces(interfaces_data)

    assert len(interfaces) == 1
    assert interfaces[0].type == NetworkInterfaceTypeStr.TUNNEL
    assert interfaces[0].type_id == NetworkInterfaceTypeId.TUNNEL


def test_build_network_interfaces_mobile():
    interfaces_data = [TenableNetworkInterface(name="mobile_test", virtual=False)]
    interfaces = TenableDeviceMapper.build_network_interfaces(interfaces_data)

    assert len(interfaces) == 1
    assert interfaces[0].type == NetworkInterfaceTypeStr.MOBILE
    assert interfaces[0].type_id == NetworkInterfaceTypeId.MOBILE


def test_build_network_interfaces_empty():
    interfaces = TenableDeviceMapper.build_network_interfaces([])
    assert interfaces == []


def test_build_device_complete(asset_info):
    device = TenableDeviceMapper(AssetInfo.model_validate(asset_info)).map()

    assert device.uid == "74a507c2-c885-41ee-a34d-e151c99e3f60"
    assert device.hostname == "moxptgljp3d450f5.example.demo"
    assert device.type == DeviceTypeStr.SERVER
    assert device.type_id == DeviceTypeId.SERVER
    assert device.os.type == OSTypeStr.SOLARIS
    assert device.os.type_id == OSTypeId.SOLARIS
    assert device.is_managed is False
    assert device.ip == "192.0.2.2"


def test_build_device_minimal():
    minimal_asset = AssetInfo(id="test-123")

    device = TenableDeviceMapper(minimal_asset).map()

    assert device.uid == "test-123"
    assert device.hostname == "unknown"
    assert device.type == DeviceTypeStr.UNKNOWN


def test_details_azure_location_maps_to_device_location():
    """Fallback-fetched Azure assets keep their Device.location via azure_location."""
    details = AssetDetails.model_validate({"id": "asset-azure", "name": "az-host", "azure_location": ["westeurope"]})
    exported = asset_details_to_export(details)
    assert exported.cloud is not None
    assert exported.cloud.azure is not None
    assert exported.cloud.azure.location == "westeurope"

    device = TenableDeviceMapper(exported).map()
    assert device.location is not None
    assert device.location.city == "westeurope"


def test_hostname_falls_back_to_name_when_no_host_or_fqdn():
    """When network hostnames/fqdns are empty, the device hostname uses the asset name, not 'unknown'."""
    asset = AssetInfo(id="asset-y", name="my-asset")
    device = TenableDeviceMapper(asset).map()
    assert device.hostname == "my-asset"
    assert device.name == "my-asset"


def test_hostname_unknown_when_no_labels_at_all():
    """With neither hostname/fqdn nor name, the device hostname falls back to 'unknown'."""
    asset = AssetInfo(id="asset-z")
    device = TenableDeviceMapper(asset).map()
    assert asset.name is None
    assert device.hostname == "unknown"


def test_export_hostname_takes_precedence_over_name(asset_info):
    """Export hostname wins over the details name fallback."""
    asset = AssetInfo.model_validate({**asset_info, "name": "asset-label"})
    device = TenableDeviceMapper(asset).map()
    assert device.hostname == "moxptgljp3d450f5.example.demo"
    assert device.name == "asset-label"


def test_hostname_name_wins_over_fqdn():
    asset = AssetInfo.model_validate(
        {"id": "asset-n", "name": "asset-label", "network": {"fqdns": ["host.example.com"]}}
    )
    device = TenableDeviceMapper(asset).map()
    assert device.hostname == "asset-label"
    assert device.name == "asset-label"


def test_hostname_falls_back_to_fqdn():
    asset = AssetInfo.model_validate({"id": "asset-f", "network": {"fqdns": ["host.example.com"]}})
    device = TenableDeviceMapper(asset).map()
    assert device.hostname == "host.example.com"
    assert device.name == "host.example.com"


def test_name_falls_back_to_hostname():
    asset = AssetInfo.model_validate(
        {"id": "asset-h", "network": {"hostnames": ["host-1"], "fqdns": ["host-1.example.com"]}}
    )
    device = TenableDeviceMapper(asset).map()
    assert device.hostname == "host-1"
    assert device.name == "host-1"


@pytest.mark.parametrize(
    "hostname, name, fqdn",
    [
        ("host-1", "asset-label", "host-1.example.com"),
        (None, "asset-label", "host-1.example.com"),
        (None, None, "host-1.example.com"),
        ("host-1", None, None),
        (None, None, None),
    ],
)
def test_hostname_parity_export_and_details(hostname, name, fqdn):
    """The same asset gives the same device hostname and name through the export and the details paths."""
    exported = AssetInfo.model_validate(
        {
            "id": "asset-p",
            "name": name,
            "network": {"hostnames": [hostname] if hostname else [], "fqdns": [fqdn] if fqdn else []},
        }
    )
    details = asset_details_to_export(
        AssetDetails.model_validate(
            {
                "id": "asset-p",
                "name": name,
                "hostname": [hostname] if hostname else [],
                "fqdn": [fqdn] if fqdn else [],
            }
        )
    )

    from_export = TenableDeviceMapper(exported).map()
    from_details = TenableDeviceMapper(details).map()

    assert (from_export.hostname, from_export.name) == (from_details.hostname, from_details.name)


def test_build_network_interface_empty_is_none():
    assert TenableDeviceMapper.build_network_interface(TenableNetworkInterface()) is None


def test_device_without_usable_interface_has_no_network_interfaces():
    asset = AssetInfo.model_validate({"id": "asset-1", "network": {"network_interfaces": [{}]}})

    assert TenableDeviceMapper(asset).map().network_interfaces is None
