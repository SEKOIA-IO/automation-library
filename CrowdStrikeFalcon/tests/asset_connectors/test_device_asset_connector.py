import pytest
from unittest.mock import Mock

from crowdstrike_falcon.asset_connectors.device_assets import CrowdstrikeDeviceAssetConnector
from sekoia_automation.asset_connector.models.ocsf.device import (
    OSTypeId,
    OSTypeStr,
    DeviceTypeId,
    DeviceTypeStr,
)


class _DummyContext:
    def __init__(self, initial=None):
        self.store = initial or {}

    def __enter__(self):
        return self.store

    def __exit__(self, exc_type, exc, tb):
        pass


@pytest.fixture
def connector():
    class FakeCrowdStrikeDeviceModule:
        configuration = {
            "sekoia_base_url": "https://api.fake.sekoia.io/",
            "frequency": 60,
            "sekoia_api_key": "fake_api_key",
            "batch_size": 100,
        }
        manifest = {
            "client_id": "fake_client_id",
            "client_secret": "fake_client_secret",
            "base_url": "https://api.fake",
        }

    c = CrowdstrikeDeviceAssetConnector(module=FakeCrowdStrikeDeviceModule())
    c.context = _DummyContext()
    c.log = Mock()
    return c


@pytest.mark.parametrize(
    "device_data,expected_name,expected_type,expected_type_id",
    [
        (
            {"platform_name": "Windows", "os_version": "Windows 11 Pro"},
            "Windows 11 Pro",
            OSTypeStr.WINDOWS,
            OSTypeId.WINDOWS,
        ),
        ({"platform_name": "Linux", "os_version": "Ubuntu 22.04"}, "Ubuntu 22.04", OSTypeStr.LINUX, OSTypeId.LINUX),
        ({"platform_name": "Mac", "os_version": "macOS Ventura"}, "macOS Ventura", OSTypeStr.MACOS, OSTypeId.MACOS),
        ({"platform_name": "macOS", "os_version": "macOS Sonoma"}, "macOS Sonoma", OSTypeStr.MACOS, OSTypeId.MACOS),
        ({"platform_name": "iOS", "os_version": "iOS 17"}, "iOS 17", OSTypeStr.IOS, OSTypeId.IOS),
        ({"platform_name": "Android", "os_version": "Android 14"}, "Android 14", OSTypeStr.ANDROID, OSTypeId.ANDROID),
        ({"platform_name": "Windows"}, "Windows", OSTypeStr.WINDOWS, OSTypeId.WINDOWS),
        (
            {"platform_name": "CustomOS", "os_version": "CustomOS 1.0"},
            "CustomOS 1.0",
            OSTypeStr.UNKNOWN,
            OSTypeId.UNKNOWN,
        ),
        ({"os_version": "Unknown OS"}, "Unknown OS", OSTypeStr.UNKNOWN, OSTypeId.UNKNOWN),
        ({}, "Unknown", OSTypeStr.UNKNOWN, OSTypeId.UNKNOWN),
    ],
)
def test_device_os_detection(device_data, expected_name, expected_type, expected_type_id, connector):
    os_obj = connector.get_device_os(device_data)
    assert os_obj.name == expected_name
    assert os_obj.type == expected_type
    assert os_obj.type_id == expected_type_id


@pytest.mark.parametrize(
    "device_data,expected_type_id,expected_type_str",
    [
        ({"product_type_desc": "Desktop"}, DeviceTypeId.DESKTOP, DeviceTypeStr.DESKTOP),
        ({"product_type_desc": "Workstation"}, DeviceTypeId.DESKTOP, DeviceTypeStr.DESKTOP),
        ({"product_type_desc": "Laptop"}, DeviceTypeId.LAPTOP, DeviceTypeStr.LAPTOP),
        ({"product_type_desc": "Server"}, DeviceTypeId.SERVER, DeviceTypeStr.SERVER),
        ({"product_type_desc": "Mobile"}, DeviceTypeId.MOBILE, DeviceTypeStr.MOBILE),
        ({"product_type_desc": "Phone"}, DeviceTypeId.MOBILE, DeviceTypeStr.MOBILE),
        ({"product_type_desc": "Tablet"}, DeviceTypeId.TABLET, DeviceTypeStr.TABLET),
        ({"product_type_desc": "Virtual"}, DeviceTypeId.VIRTUAL, DeviceTypeStr.VIRTUAL),
        ({"product_type_desc": "Appliance"}, DeviceTypeId.UNKNOWN, DeviceTypeStr.UNKNOWN),
        ({"product_type_desc": ""}, DeviceTypeId.UNKNOWN, DeviceTypeStr.UNKNOWN),
        ({}, DeviceTypeId.UNKNOWN, DeviceTypeStr.UNKNOWN),
    ],
)
def test_device_type_mapping(device_data, expected_type_id, expected_type_str, connector):
    type_id, type_str = connector.get_device_type(device_data)
    assert type_id == expected_type_id
    assert type_str == expected_type_str


def test_get_firewall_status_enabled(connector):
    device = {"device_policies": {"firewall": {"applied": True}}}
    status = connector.get_firewall_status(device)
    assert status == "Enabled"


def test_get_firewall_status_disabled(connector):
    device = {"device_policies": {"firewall": {"applied": False}}}
    status = connector.get_firewall_status(device)
    assert status == "Disabled"


def test_get_firewall_status_missing(connector):
    device = {"device_policies": {}}
    status = connector.get_firewall_status(device)
    assert status == "Disabled"


def test_map_device_fields_firewall_enabled(connector):
    device = {
        "device_id": "dev1",
        "hostname": "host1",
        "platform_name": "Windows",
        "os_version": "Windows 10",
        "product_type_desc": "Desktop",
        "device_policies": {"firewall": {"applied": True}},
    }
    model = connector.map_device_fields(device)
    assert model.device.uid == "dev1"
    assert model.device.os.type_id == OSTypeId.WINDOWS
    assert model.device.type_id == DeviceTypeId.DESKTOP
    assert model.enrichments[0].data.Firewall_status == "Enabled"


def test_map_device_fields_firewall_disabled_and_unknown_type(connector):
    device = {
        "device_id": "dev2",
        "hostname": "host2",
        "platform_name": "AlienOS",
        "product_type_desc": "Blender",
        "device_policies": {"firewall": {"applied": False}},
    }
    model = connector.map_device_fields(device)
    assert model.device.os.type_id == OSTypeId.UNKNOWN
    assert model.device.type_id == DeviceTypeId.UNKNOWN
    assert model.enrichments[0].data.Firewall_status == "Disabled"


def test_update_checkpoint_no_latest_id_no_write(connector):
    connector.update_checkpoint()
    assert "most_recent_device_id" not in connector.context.store


def test_update_checkpoint_writes_key_but_property_reads_other_key(connector):
    connector._latest_id = "abc123"
    connector.update_checkpoint()
    assert connector.context.store["most_recent_device_id"] == "abc123"
    assert connector.most_recent_device_id == "abc123"


def test_next_devices_no_new_device_returns_empty_and_logs(connector):
    first_uuid = "u1"
    connector.context.store["most_recent_device_id"] = first_uuid
    client = Mock()
    client.list_devices_uuids.return_value = [first_uuid]
    connector.client = client
    result = list(connector.next_devices())
    assert result == []
    connector.log.assert_called_once()
    assert connector._latest_id is None


def test_next_devices_batches_and_stops_on_checkpoint(connector):
    connector.LIMIT = 2
    connector.context.store["most_recent_device_id"] = "u3"
    client = Mock()
    client.list_devices_uuids.return_value = ["u5", "u4", "u3", "u2"]

    def get_infos(batch):
        return [{"device_id": b} for b in batch]

    client.get_devices_infos.side_effect = get_infos
    connector.client = client
    collected = list(connector.next_devices())
    assert [d["device_id"] for d in collected] == ["u5", "u4"]
    client.get_devices_infos.assert_called_once_with(["u5", "u4"])
    assert connector._latest_id == "u5"


def test_next_devices_multiple_batches_and_flush_last(connector):
    connector.LIMIT = 2
    client = Mock()
    client.list_devices_uuids.return_value = ["u5", "u4", "u3"]

    def get_infos(batch):
        return [{"device_id": b} for b in batch]

    client.get_devices_infos.side_effect = get_infos
    connector.client = client
    collected = list(connector.next_devices())
    assert [d["device_id"] for d in collected] == ["u5", "u4", "u3"]
    assert client.get_devices_infos.call_count == 2
    client.get_devices_infos.assert_any_call(["u5", "u4"])
    client.get_devices_infos.assert_any_call(["u3"])
    assert connector._latest_id == "u5"


def test_get_assets_yields_mapped_models(monkeypatch, connector):
    sample_devices = [
        {
            "device_id": "d1",
            "hostname": "h1",
            "platform_name": "Linux",
            "product_type_desc": "Server",
            "device_policies": {"firewall": {"applied": True}},
        },
        {
            "device_id": "d2",
            "hostname": "h2",
            "platform_name": "Mac",
            "product_type_desc": "Laptop",
            "device_policies": {"firewall": {"applied": False}},
        },
    ]
    monkeypatch.setattr(connector, "next_devices", lambda: iter(sample_devices))
    results = list(connector.get_assets())
    assert len(results) == 2
    assert results[0].device.uid == "d1"
    assert results[1].device.uid == "d2"
    assert results[0].enrichments[0].data.Firewall_status == "Enabled"
    assert results[1].enrichments[0].data.Firewall_status == "Disabled"


@pytest.mark.parametrize(
    "ts,expected",
    [
        ("2024-01-15T10:30:00Z", 1705314600.0),
        ("", None),
        (None, None),
        ("invalid-date", None),
    ],
)
def test_parse_timestamp(ts, expected, connector):
    result = connector.parse_timestamp(ts)
    if expected is None:
        assert result is None
    else:
        assert abs(result - expected) < 1


@pytest.mark.parametrize(
    "mac,expected",
    [
        ("00-1a-2b-3c-4d-5e", "00:1A:2B:3C:4D:5E"),
        ("00:1a:2b:3c:4d:5e", "00:1A:2B:3C:4D:5E"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_mac_address(mac, expected, connector):
    assert connector.normalize_mac_address(mac) == expected


def test_get_network_interfaces(connector):
    device = {
        "local_ip": "192.168.1.10",
        "mac_address": "00-1a-2b-3c-4d-5e",
        "hostname": "host1",
        "connection_ip": "10.0.0.1",
    }
    interfaces = connector.get_network_interfaces(device)
    assert len(interfaces) == 2
    assert interfaces[0].ip == "192.168.1.10"
    assert interfaces[0].mac == "00:1A:2B:3C:4D:5E"


def test_get_organization(connector):
    device = {"cid": "org-123", "service_provider": "Acme Corp"}
    org = connector.get_organization(device)
    assert org.uid == "org-123"
    assert org.name == "Acme Corp"


def test_get_organization_missing_cid(connector):
    device = {"service_provider": "Acme Corp"}
    assert connector.get_organization(device) is None


def test_get_groups(connector):
    device = {"groups": ["group1", "group2"]}

    mock_client = Mock()
    mock_client.get_host_groups.return_value = [
        {"id": "group1", "name": "Group One", "description": "First group", "group_type": "static"},
        {"id": "group2", "name": "Group Two", "description": "", "group_type": "dynamic"},
    ]
    connector.client = mock_client

    groups = connector.get_groups(device)

    assert len(groups) == 2
    assert groups[0].uid == "group1"
    assert groups[0].name == "Group One"
    assert groups[0].desc == "First group"
    assert groups[1].name == "Group Two"
    assert groups[1].desc is None


def test_get_groups_api_failure_fallback(connector):
    device = {"groups": ["group1"]}

    mock_client = Mock()
    mock_client.get_host_groups.side_effect = Exception("API error")
    connector.client = mock_client

    groups = connector.get_groups(device)

    assert len(groups) == 1
    assert groups[0].uid == "group1"
    assert groups[0].name == "group1"  # Fallback


def test_is_device_compliant(connector):
    compliant = {"status": "normal", "reduced_functionality_mode": "no", "filesystem_containment_status": "normal"}
    non_compliant = {
        "status": "contained",
        "reduced_functionality_mode": "yes",
        "filesystem_containment_status": "contained",
    }

    assert connector.is_device_compliant(compliant) is True
    assert connector.is_device_compliant(non_compliant) is False
    assert connector.is_device_compliant({}) is None
