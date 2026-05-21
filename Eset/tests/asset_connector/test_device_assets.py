import json
from unittest.mock import Mock, MagicMock, patch

import pytest
import requests
import requests_mock as requests_mock_module

from eset_modules import EsetModule
from eset_modules.asset_connector.device_assets import EsetDeviceAssetConnector
from eset_modules.asset_connector.models import (
    EsetDevice,
    EsetDeviceGroup,
    EsetHardwareProfile,
    EsetNetworkAdapter,
    EsetOperatingSystem,
    EsetOsVersion,
)
from eset_modules.models import EsetModuleConfiguration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def data_storage(tmp_path):
    return tmp_path


@pytest.fixture
def test_connector(data_storage):
    module = EsetModule()
    module.configuration = EsetModuleConfiguration(
        region="eu",
        username="testuser",
        password="testpassword",
    )

    connector = EsetDeviceAssetConnector(module=module, data_path=data_storage)
    connector.configuration = {
        "sekoia_base_url": "https://sekoia.io",
        "sekoia_api_key": "fake_api_key",
        "frequency": 60,
    }

    connector.log = Mock()
    connector.log_exception = Mock()

    # Inject a real requests.Session as the client so tests can use requests_mock
    # without needing to mock the OAuth token endpoint
    real_session = requests.Session()
    connector.__dict__["client"] = real_session

    yield connector


@pytest.fixture
def sample_device() -> EsetDevice:
    return EsetDevice(
        uuid="550e8400-e29b-41d4-a716-446655440000",
        displayName="DESKTOP-ABC123",
        description="Finance workstation",
        deviceType="DEVICE_TYPE_DESKTOP",
        isMobile=False,
        isMaster=True,
        isMuted=False,
        lastSyncTime="2026-05-21T10:00:00Z",
        parentGroupUuid="group-uuid-1",
        primaryLocalIpAddress="192.168.1.42",
        publicIpAddress="203.0.113.10",
        tags=["finance", "windows"],
        operatingSystem=EsetOperatingSystem(
            bitness=64,
            displayName="Windows 10 Enterprise",
            familyId=1,
            version=EsetOsVersion(id="10.0.19041", major=10, minor=0, name="Windows 10", patch=19041),
        ),
        hardwareProfiles=[
            EsetHardwareProfile(
                manufacturer="Dell Inc.",
                model="Latitude 5520",
                networkAdapters=[
                    EsetNetworkAdapter(
                        caption="Intel(R) Ethernet Connection",
                        macAddress="AA:BB:CC:DD:EE:FF",
                    )
                ],
            )
        ],
    )


@pytest.fixture
def sample_group() -> EsetDeviceGroup:
    return EsetDeviceGroup(
        uuid="group-uuid-1",
        displayName="Finance Department",
        isSecurityGroup=False,
        parentGroupUuid="root-group-uuid",
    )


@pytest.fixture
def sample_devices_response():
    return {
        "devices": [
            {
                "uuid": "550e8400-e29b-41d4-a716-446655440000",
                "displayName": "DESKTOP-ABC123",
                "description": "Finance workstation",
                "deviceType": "DEVICE_TYPE_DESKTOP",
                "isMobile": False,
                "lastSyncTime": "2026-05-21T10:00:00Z",
                "parentGroupUuid": "group-uuid-1",
                "primaryLocalIpAddress": "192.168.1.42",
                "operatingSystem": {
                    "displayName": "Windows 10 Enterprise",
                    "familyId": 1,
                },
                "hardwareProfiles": [
                    {
                        "model": "Latitude 5520",
                        "networkAdapters": [{"caption": "Intel Ethernet", "macAddress": "AA:BB:CC:DD:EE:FF"}],
                    }
                ],
            }
        ],
        "nextPageToken": None,
    }


@pytest.fixture
def sample_groups_response():
    return {
        "deviceGroups": [
            {
                "uuid": "group-uuid-1",
                "displayName": "Finance Department",
                "isSecurityGroup": False,
                "parentGroupUuid": "root-group-uuid",
            }
        ],
        "nextPageToken": None,
    }


# ---------------------------------------------------------------------------
# Unit tests — build_operating_system
# ---------------------------------------------------------------------------


def test_build_operating_system_windows(test_connector, sample_device):
    os = test_connector.build_operating_system(sample_device)
    assert os is not None
    assert os.name == "Windows 10 Enterprise"
    assert os.type.value == "windows"
    assert os.type_id == 100


def test_build_operating_system_linux(test_connector):
    device = EsetDevice(
        uuid="abc",
        operatingSystem=EsetOperatingSystem(displayName="Ubuntu 22.04", familyId=3),
    )
    os = test_connector.build_operating_system(device)
    assert os is not None
    assert os.type.value == "linux"
    assert os.type_id == 200


def test_build_operating_system_unknown_family(test_connector):
    device = EsetDevice(uuid="abc", operatingSystem=EsetOperatingSystem(displayName="SomeOS", familyId=99))
    os = test_connector.build_operating_system(device)
    assert os is not None
    assert os.type_id == 99  # OTHER


def test_build_operating_system_no_os(test_connector):
    device = EsetDevice(uuid="abc")
    assert test_connector.build_operating_system(device) is None


# ---------------------------------------------------------------------------
# Unit tests — build_network_interfaces
# ---------------------------------------------------------------------------


def test_build_network_interfaces_with_ip_and_mac(test_connector, sample_device):
    interfaces = test_connector.build_network_interfaces(sample_device)
    assert interfaces is not None
    assert len(interfaces) == 1
    assert interfaces[0].ip == "192.168.1.42"
    assert interfaces[0].mac == "AA:BB:CC:DD:EE:FF"
    assert interfaces[0].name == "Intel(R) Ethernet Connection"


def test_build_network_interfaces_no_data(test_connector):
    device = EsetDevice(uuid="abc")
    assert test_connector.build_network_interfaces(device) is None


def test_build_network_interfaces_ip_only(test_connector):
    device = EsetDevice(uuid="abc", primaryLocalIpAddress="10.0.0.1")
    interfaces = test_connector.build_network_interfaces(device)
    assert interfaces is not None
    assert interfaces[0].ip == "10.0.0.1"
    assert interfaces[0].mac is None


# ---------------------------------------------------------------------------
# Unit tests — _resolve_device_type
# ---------------------------------------------------------------------------


def test_resolve_device_type_mobile(test_connector):
    device = EsetDevice(uuid="abc", isMobile=True)
    type_str, type_id = test_connector._resolve_device_type(device)
    assert type_id == 5  # MOBILE


def test_resolve_device_type_server(test_connector):
    device = EsetDevice(uuid="abc", deviceType="DEVICE_TYPE_SERVER")
    type_str, type_id = test_connector._resolve_device_type(device)
    assert type_id == 1  # SERVER


def test_resolve_device_type_desktop_default(test_connector):
    device = EsetDevice(uuid="abc", isMobile=False, deviceType="DEVICE_TYPE_DESKTOP")
    type_str, type_id = test_connector._resolve_device_type(device)
    assert type_id == 2  # DESKTOP


# ---------------------------------------------------------------------------
# Unit tests — build_device
# ---------------------------------------------------------------------------


def test_build_device_basic(test_connector, sample_device, sample_group):
    device = test_connector.build_device(sample_device, [sample_group])
    assert device.uid == "550e8400-e29b-41d4-a716-446655440000"
    assert device.hostname == "DESKTOP-ABC123"
    assert device.ip == "192.168.1.42"
    assert device.model == "Latitude 5520"
    assert device.is_managed is True
    assert device.groups is not None
    assert device.groups[0].name == "Finance Department"
    assert device.groups[0].uid == "group-uuid-1"


def test_build_device_no_groups(test_connector, sample_device):
    device = test_connector.build_device(sample_device, [])
    assert device.groups is None


def test_build_device_hostname_fallback(test_connector):
    device = EsetDevice(uuid="my-uuid", originalDisplayName="ORIG-NAME")
    result = test_connector.build_device(device, [])
    assert result.hostname == "ORIG-NAME"


def test_build_device_hostname_uuid_fallback(test_connector):
    device = EsetDevice(uuid="my-uuid")
    result = test_connector.build_device(device, [])
    assert result.hostname == "my-uuid"


# ---------------------------------------------------------------------------
# Unit tests — map_fields
# ---------------------------------------------------------------------------


def test_map_fields_ocsf_classification(test_connector, sample_device, sample_group):
    from sekoia_automation.asset_connector.models.ocsf.device import DeviceOCSFModel

    result = test_connector.map_fields(sample_device, [sample_group])
    assert isinstance(result, DeviceOCSFModel)
    assert result.class_uid == 5001
    assert result.type_uid == 500102
    assert result.activity_id == 2
    assert result.activity_name == "Collect"
    assert result.category_uid == 5


def test_map_fields_metadata(test_connector, sample_device):
    result = test_connector.map_fields(sample_device, [])
    assert result.metadata.product.name == "ESET EDR"
    assert result.metadata.version == "1.5.0"


def test_map_fields_device_uid(test_connector, sample_device):
    result = test_connector.map_fields(sample_device, [])
    assert result.device.uid == "550e8400-e29b-41d4-a716-446655440000"


def test_map_fields_json_serializable(test_connector, sample_device, sample_group):
    result = test_connector.map_fields(sample_device, [sample_group])
    json_data = result.model_dump()
    serialized = json.dumps(json_data)
    assert serialized
    assert json_data["class_uid"] == 5001


def test_map_fields_no_last_sync_time_uses_utcnow(test_connector):
    device = EsetDevice(uuid="abc", displayName="HOST", lastSyncTime=None)
    result = test_connector.map_fields(device, [])
    assert result.time is not None
    assert result.time > 0


# ---------------------------------------------------------------------------
# Fetch method tests (with requests_mock)
# ---------------------------------------------------------------------------


def test_fetch_all_groups_single_page(test_connector, sample_groups_response):
    with requests_mock_module.Mocker() as m:
        m.get(
            f"{test_connector.base_url}/v1/device_groups",
            json=sample_groups_response,
        )
        groups = test_connector._fetch_all_groups()

    assert len(groups) == 1
    assert "group-uuid-1" in groups
    assert groups["group-uuid-1"].displayName == "Finance Department"


def test_fetch_all_groups_pagination(test_connector):
    page1 = {
        "deviceGroups": [{"uuid": "g1", "displayName": "Group 1"}],
        "nextPageToken": "token123",
    }
    page2 = {
        "deviceGroups": [{"uuid": "g2", "displayName": "Group 2"}],
        "nextPageToken": None,
    }
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/device_groups", [{"json": page1}, {"json": page2}])
        groups = test_connector._fetch_all_groups()

    assert len(groups) == 2
    assert "g1" in groups
    assert "g2" in groups


def test_fetch_all_groups_api_error(test_connector):
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/device_groups", status_code=500)
        groups = test_connector._fetch_all_groups()

    assert groups == {}
    test_connector.log.assert_called()


def test_fetch_devices_single_page(test_connector, sample_devices_response):
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/devices", json=sample_devices_response)
        pages = list(test_connector._fetch_devices())

    assert len(pages) == 1
    assert len(pages[0]) == 1
    assert pages[0][0].uuid == "550e8400-e29b-41d4-a716-446655440000"


def test_fetch_devices_pagination(test_connector):
    page1 = {
        "devices": [{"uuid": "dev-1", "displayName": "Device 1", "lastSyncTime": "2026-05-20T09:00:00Z"}],
        "nextPageToken": "token-page2",
    }
    page2 = {
        "devices": [{"uuid": "dev-2", "displayName": "Device 2", "lastSyncTime": "2026-05-21T09:00:00Z"}],
        "nextPageToken": None,
    }
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/devices", [{"json": page1}, {"json": page2}])
        pages = list(test_connector._fetch_devices())

    assert len(pages) == 2
    assert pages[0][0].uuid == "dev-1"
    assert pages[1][0].uuid == "dev-2"


def test_fetch_devices_empty(test_connector):
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/devices", json={"devices": [], "nextPageToken": None})
        pages = list(test_connector._fetch_devices())

    assert len(pages) == 0


def test_fetch_devices_api_error(test_connector):
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/devices", status_code=500)
        with pytest.raises(Exception):
            list(test_connector._fetch_devices())


# ---------------------------------------------------------------------------
# Integration test — get_assets
# ---------------------------------------------------------------------------


def test_get_assets_yields_ocsf_models(test_connector, sample_devices_response, sample_groups_response):
    from sekoia_automation.asset_connector.models.ocsf.device import DeviceOCSFModel

    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/device_groups", json=sample_groups_response)
        m.get(f"{test_connector.base_url}/v1/devices", json=sample_devices_response)

        with patch.object(
            type(test_connector),
            "most_recent_date_seen",
            new_callable=lambda: property(lambda self: None),
        ):
            assets = list(test_connector.get_assets())

    assert len(assets) == 1
    assert isinstance(assets[0], DeviceOCSFModel)
    assert assets[0].device.uid == "550e8400-e29b-41d4-a716-446655440000"
    assert assets[0].device.groups is not None
    assert assets[0].device.groups[0].name == "Finance Department"


def test_get_assets_no_devices(test_connector):
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/device_groups", json={"deviceGroups": [], "nextPageToken": None})
        m.get(f"{test_connector.base_url}/v1/devices", json={"devices": [], "nextPageToken": None})

        assets = list(test_connector.get_assets())

    assert assets == []


def test_get_assets_device_without_group(test_connector):
    devices_response = {
        "devices": [{"uuid": "dev-no-group", "displayName": "Orphan", "lastSyncTime": "2026-05-21T10:00:00Z"}],
        "nextPageToken": None,
    }
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/device_groups", json={"deviceGroups": [], "nextPageToken": None})
        m.get(f"{test_connector.base_url}/v1/devices", json=devices_response)

        assets = list(test_connector.get_assets())

    assert len(assets) == 1
    assert assets[0].device.groups is None


# ---------------------------------------------------------------------------
# Checkpoint tests
# ---------------------------------------------------------------------------


def test_update_checkpoint_persists(test_connector, sample_devices_response, sample_groups_response):
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/device_groups", json=sample_groups_response)
        m.get(f"{test_connector.base_url}/v1/devices", json=sample_devices_response)

        list(test_connector.get_assets())
        test_connector.update_checkpoint()

    checkpoint = test_connector.most_recent_date_seen
    assert checkpoint is not None


def test_update_checkpoint_no_devices(test_connector):
    # No devices → _latest_time stays None → update_checkpoint is a no-op
    test_connector.update_checkpoint()
    assert test_connector.most_recent_date_seen is None
