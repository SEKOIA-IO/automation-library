import json
from unittest.mock import Mock, MagicMock, patch

import pytest
import requests
import requests_mock as requests_mock_module

from eset_modules import EsetModule
from eset_modules.asset_connector.device_assets import EsetDeviceAssetConnector
from eset_modules.asset_connector.models import (
    EsetActiveProduct,
    EsetActivateDate,
    EsetCloningConfiguration,
    EsetDeployedComponent,
    EsetDevice,
    EsetDeviceGroup,
    EsetHardwareProfile,
    EsetNetworkAdapter,
    EsetOperatingSystem,
    EsetOsVersion,
)
from eset_modules.models import EsetModuleConfiguration
from sekoia_automation.asset_connector.models.ocsf.device import NetworkInterfaceTypeId


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
        managementDomain="eu.automation.eset.systems",
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
        deployedComponents=[
            EsetDeployedComponent(
                displayName="ESET Endpoint Security",
                version=EsetOsVersion(
                    id="10.0.2045.0", major=10, minor=0, name="ESET Endpoint Security 10.0", patch=2045
                ),
                id=1,
                name="eea",
            )
        ],
        activeProducts=[
            EsetActiveProduct(
                activateDate=EsetActivateDate(year=2025, month=1, day=15),
                subscriptionUuid="sub-uuid-123",
                unitPoolUuid="pool-uuid-456",
                validityDate=EsetActivateDate(year=2026, month=1, day=15),
                id=10,
                name="ESET PROTECT Entry",
            )
        ],
        cloningConfiguration=EsetCloningConfiguration(
            cloneNamingPatterns=["DESKTOP-*"],
            securityGroupUuid="sec-group-uuid-1",
            securityGroupDisplayName="Default Security Group",
        ),
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


def test_build_network_interfaces_with_ip_and_mac(test_connector, sample_device):
    interfaces = test_connector.build_network_interfaces(sample_device)
    assert interfaces is not None
    assert len(interfaces) == 2  # primary local IP (enriched) + public IP
    # First interface: local IP enriched with MAC from adapter "Intel(R) Ethernet Connection" → WIRED
    assert interfaces[0].ip == "192.168.1.42"
    assert interfaces[0].mac == "AA:BB:CC:DD:EE:FF"
    assert interfaces[0].name == "Intel(R) Ethernet Connection"
    assert interfaces[0].type_id == NetworkInterfaceTypeId.WIRED
    # Second interface: public IP
    assert interfaces[1].ip == "203.0.113.10"


def test_build_network_interfaces_wifi_detection(test_connector):
    device = EsetDevice(
        uuid="abc",
        primaryLocalIpAddress="192.168.1.10",
        hardwareProfiles=[
            EsetHardwareProfile(
                networkAdapters=[EsetNetworkAdapter(caption="Intel Wi-Fi 6 AX201", macAddress="11:22:33:44:55:66")]
            )
        ],
    )
    interfaces = test_connector.build_network_interfaces(device)
    assert interfaces is not None
    assert interfaces[0].type_id == NetworkInterfaceTypeId.WIRELESS


def test_build_network_interfaces_unknown_type_when_no_caption(test_connector):
    device = EsetDevice(
        uuid="abc",
        primaryLocalIpAddress="10.0.0.1",
        hardwareProfiles=[
            EsetHardwareProfile(networkAdapters=[EsetNetworkAdapter(caption=None, macAddress="AA:BB:CC:DD:EE:FF")])
        ],
    )
    interfaces = test_connector.build_network_interfaces(device)
    assert interfaces is not None
    assert interfaces[0].type_id == NetworkInterfaceTypeId.UNKNOWN


def test_build_network_interfaces_multiple_adapters_enrich_correctly(test_connector):
    """Two adapters: first enriches the IP interface, second creates a new MAC-only interface."""
    device = EsetDevice(
        uuid="abc",
        primaryLocalIpAddress="10.0.0.1",
        hardwareProfiles=[
            EsetHardwareProfile(
                networkAdapters=[
                    EsetNetworkAdapter(caption="Realtek Ethernet", macAddress="AA:AA:AA:AA:AA:AA"),
                    EsetNetworkAdapter(caption="Intel Wi-Fi", macAddress="BB:BB:BB:BB:BB:BB"),
                ]
            )
        ],
    )
    interfaces = test_connector.build_network_interfaces(device)
    assert interfaces is not None
    assert len(interfaces) == 2
    # First interface has IP + first adapter's MAC
    assert interfaces[0].ip == "10.0.0.1"
    assert interfaces[0].mac == "AA:AA:AA:AA:AA:AA"
    assert interfaces[0].type_id == NetworkInterfaceTypeId.WIRED
    # Second interface has only the second adapter's MAC (no IP)
    assert interfaces[1].ip is None
    assert interfaces[1].mac == "BB:BB:BB:BB:BB:BB"
    assert interfaces[1].type_id == NetworkInterfaceTypeId.WIRELESS


def test_build_network_interfaces_public_ip_same_as_local(test_connector):
    device = EsetDevice(uuid="abc", primaryLocalIpAddress="10.0.0.1", publicIpAddress="10.0.0.1")
    interfaces = test_connector.build_network_interfaces(device)
    # Public IP equals local → not duplicated
    assert interfaces is not None
    assert len(interfaces) == 1


def test_build_network_interfaces_public_ip_only(test_connector):
    device = EsetDevice(uuid="abc", publicIpAddress="203.0.113.10")
    interfaces = test_connector.build_network_interfaces(device)
    assert interfaces is not None
    assert len(interfaces) == 1
    assert interfaces[0].ip == "203.0.113.10"


def test_build_network_interfaces_no_data(test_connector):
    device = EsetDevice(uuid="abc")
    assert test_connector.build_network_interfaces(device) is None


def test_build_network_interfaces_ip_only(test_connector):
    device = EsetDevice(uuid="abc", primaryLocalIpAddress="10.0.0.1")
    interfaces = test_connector.build_network_interfaces(device)
    assert interfaces is not None
    assert interfaces[0].ip == "10.0.0.1"
    assert interfaces[0].mac is None


def test_build_network_interfaces_hostname_uses_resolved_hostname(test_connector):
    """hostname on the network interface should match the resolved device hostname, not just displayName."""
    device = EsetDevice(uuid="my-uuid", originalDisplayName="ORIG-NAME", primaryLocalIpAddress="10.0.0.1")
    interfaces = test_connector.build_network_interfaces(device)
    assert interfaces is not None
    assert interfaces[0].hostname == "ORIG-NAME"  # falls back to originalDisplayName, not None


def test_build_network_interfaces_hostname_falls_back_to_uuid(test_connector):
    """If displayName and originalDisplayName are both None, hostname should be the uuid."""
    device = EsetDevice(uuid="my-uuid", primaryLocalIpAddress="10.0.0.1")
    interfaces = test_connector.build_network_interfaces(device)
    assert interfaces is not None
    assert interfaces[0].hostname == "my-uuid"


def test_build_device_network_interface_hostname_consistent(test_connector):
    """device.hostname and device.network_interfaces[0].hostname must always be identical."""
    device = EsetDevice(uuid="my-uuid", originalDisplayName="ORIG-NAME", primaryLocalIpAddress="10.0.0.1")
    result = test_connector.build_device(device, [])
    assert result.hostname == "ORIG-NAME"
    assert result.network_interfaces is not None
    assert result.network_interfaces[0].hostname == result.hostname


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


def test_build_device_basic(test_connector, sample_device, sample_group):
    device = test_connector.build_device(sample_device, [sample_group])
    assert device.uid == "550e8400-e29b-41d4-a716-446655440000"
    assert device.hostname == "DESKTOP-ABC123"
    assert device.ip == "192.168.1.42"
    assert device.model == "Latitude 5520"
    assert device.vendor_name == "Dell Inc."
    assert device.domain == "eu.automation.eset.systems"
    assert device.is_managed is True
    assert device.groups is not None
    assert device.groups[0].name == "Finance Department"
    assert device.groups[0].uid == "group-uuid-1"


def test_build_device_no_groups(test_connector, sample_device):
    device = test_connector.build_device(sample_device, [])
    assert device.groups is None


def test_build_device_vendor_name_from_hardware_profile(test_connector):
    device = EsetDevice(
        uuid="abc",
        hardwareProfiles=[EsetHardwareProfile(manufacturer="HP Inc.", model="EliteBook 840")],
    )
    result = test_connector.build_device(device, [])
    assert result.vendor_name == "HP Inc."
    assert result.model == "EliteBook 840"


def test_build_device_vendor_name_none_without_hardware_profile(test_connector):
    device = EsetDevice(uuid="abc")
    result = test_connector.build_device(device, [])
    assert result.vendor_name is None


def test_build_device_domain_from_management_domain(test_connector):
    device = EsetDevice(uuid="abc", managementDomain="eu.automation.eset.systems")
    result = test_connector.build_device(device, [])
    assert result.domain == "eu.automation.eset.systems"


def test_build_device_domain_none_without_management_domain(test_connector):
    device = EsetDevice(uuid="abc")
    result = test_connector.build_device(device, [])
    assert result.domain is None


def test_build_device_hostname_fallback(test_connector):
    device = EsetDevice(uuid="my-uuid", originalDisplayName="ORIG-NAME")
    result = test_connector.build_device(device, [])
    assert result.hostname == "ORIG-NAME"


def test_build_device_hostname_uuid_fallback(test_connector):
    device = EsetDevice(uuid="my-uuid")
    result = test_connector.build_device(device, [])
    assert result.hostname == "my-uuid"


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


def test_iterate_devices_skips_already_seen(test_connector):
    """Devices with lastSyncTime <= checkpoint should be skipped."""
    devices_response = {
        "devices": [
            {"uuid": "dev-old", "displayName": "Old", "lastSyncTime": "2026-05-20T09:00:00Z"},
            {"uuid": "dev-new", "displayName": "New", "lastSyncTime": "2026-05-22T09:00:00Z"},
        ],
        "nextPageToken": None,
    }
    # Checkpoint set to 2026-05-21 → dev-old (May 20) should be skipped
    with test_connector.context as cache:
        cache["most_recent_date_seen"] = "2026-05-21T00:00:00+00:00"

    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/devices", json=devices_response)
        pages = list(test_connector.iterate_devices())

    all_devices = [d for page in pages for d in page]
    uuids = [d.uuid for d in all_devices]
    assert "dev-new" in uuids
    assert "dev-old" not in uuids


def test_iterate_devices_includes_no_last_sync_time(test_connector):
    """Devices with no lastSyncTime should always be included regardless of checkpoint."""
    devices_response = {
        "devices": [
            {"uuid": "dev-no-time", "displayName": "NoTime"},
            {"uuid": "dev-old", "displayName": "Old", "lastSyncTime": "2026-05-20T09:00:00Z"},
        ],
        "nextPageToken": None,
    }
    with test_connector.context as cache:
        cache["most_recent_date_seen"] = "2026-05-21T00:00:00+00:00"

    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/devices", json=devices_response)
        pages = list(test_connector.iterate_devices())

    all_devices = [d for page in pages for d in page]
    uuids = [d.uuid for d in all_devices]
    assert "dev-no-time" in uuids
    assert "dev-old" not in uuids


def test_iterate_devices_no_checkpoint_yields_all(test_connector):
    """Without a checkpoint, all devices should be yielded."""
    devices_response = {
        "devices": [
            {"uuid": "dev-1", "lastSyncTime": "2026-05-20T09:00:00Z"},
            {"uuid": "dev-2", "lastSyncTime": "2026-05-21T09:00:00Z"},
        ],
        "nextPageToken": None,
    }
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/devices", json=devices_response)
        pages = list(test_connector.iterate_devices())

    all_devices = [d for page in pages for d in page]
    assert len(all_devices) == 2


def test_iterate_devices_checkpoint_updated_to_max_even_if_all_skipped(test_connector):
    """Even if all devices are skipped, _latest_time should not regress."""
    devices_response = {
        "devices": [
            {"uuid": "dev-1", "lastSyncTime": "2026-05-20T09:00:00Z"},
        ],
        "nextPageToken": None,
    }
    with test_connector.context as cache:
        cache["most_recent_date_seen"] = "2026-05-21T00:00:00+00:00"

    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/devices", json=devices_response)
        list(test_connector.iterate_devices())

    # All devices skipped → max_date (May 20) < checkpoint (May 21) → _latest_time not updated
    assert not hasattr(test_connector, "_latest_time") or test_connector._latest_time is None


def test_iterate_devices_device_at_exact_checkpoint_boundary_is_skipped(test_connector):
    """A device whose lastSyncTime is exactly equal to the checkpoint must be skipped (<=)."""
    checkpoint = "2026-05-21T10:00:00+00:00"
    devices_response = {
        "devices": [
            {"uuid": "dev-exact", "lastSyncTime": "2026-05-21T10:00:00Z"},
            {"uuid": "dev-after", "lastSyncTime": "2026-05-21T10:00:01Z"},
        ],
        "nextPageToken": None,
    }
    with test_connector.context as cache:
        cache["most_recent_date_seen"] = checkpoint

    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/devices", json=devices_response)
        pages = list(test_connector.iterate_devices())

    uuids = [d.uuid for page in pages for d in page]
    assert "dev-exact" not in uuids  # exactly at checkpoint → skipped
    assert "dev-after" in uuids  # 1 second after → included


def test_iterate_devices_checkpoint_advances_to_newest_date(test_connector):
    """After a run, _latest_time should be set to the newest lastSyncTime seen + 1µs."""
    devices_response = {
        "devices": [
            {"uuid": "dev-1", "lastSyncTime": "2026-05-20T09:00:00Z"},
            {"uuid": "dev-2", "lastSyncTime": "2026-05-22T12:00:00Z"},
            {"uuid": "dev-3", "lastSyncTime": "2026-05-21T00:00:00Z"},
        ],
        "nextPageToken": None,
    }
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/devices", json=devices_response)
        list(test_connector.iterate_devices())

    # _latest_time should be the newest date (May 22) + 1µs
    assert test_connector._latest_time is not None
    assert "2026-05-22T12:00:00.000001" in test_connector._latest_time


def test_iterate_devices_mixed_pages_filter_correctly(test_connector):
    """Across multiple pages, old devices are skipped and new ones are yielded."""
    page1 = {
        "devices": [
            {"uuid": "old-1", "lastSyncTime": "2026-05-19T00:00:00Z"},
            {"uuid": "new-1", "lastSyncTime": "2026-05-22T00:00:00Z"},
        ],
        "nextPageToken": "token2",
    }
    page2 = {
        "devices": [
            {"uuid": "old-2", "lastSyncTime": "2026-05-20T00:00:00Z"},
            {"uuid": "new-2", "lastSyncTime": "2026-05-23T00:00:00Z"},
        ],
        "nextPageToken": None,
    }
    with test_connector.context as cache:
        cache["most_recent_date_seen"] = "2026-05-21T00:00:00+00:00"

    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/devices", [{"json": page1}, {"json": page2}])
        pages = list(test_connector.iterate_devices())

    uuids = [d.uuid for page in pages for d in page]
    assert set(uuids) == {"new-1", "new-2"}
    assert "old-1" not in uuids
    assert "old-2" not in uuids


def test_iterate_devices_max_date_initialized_from_latest_time(test_connector):
    """If _latest_time is already set (e.g. from a previous retry), max_date starts from it."""
    # Simulate a previous partial run that set _latest_time to May 25
    test_connector._latest_time = "2026-05-25T00:00:00+00:00"

    # Now fetch devices older than May 25 → max_date should not regress
    devices_response = {
        "devices": [
            {"uuid": "dev-old", "lastSyncTime": "2026-05-23T00:00:00Z"},
        ],
        "nextPageToken": None,
    }
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/devices", json=devices_response)
        list(test_connector.iterate_devices())

    # max_date starts at May 25 → device May 23 doesn't move it forward → _latest_time stays at May 25
    assert "2026-05-25" in test_connector._latest_time


def test_iterate_devices_second_run_uses_first_run_checkpoint(test_connector, sample_groups_response):
    """Simulate two consecutive runs: second run should only yield devices newer than first run's checkpoint."""
    devices_run1 = {
        "devices": [
            {"uuid": "dev-a", "lastSyncTime": "2026-05-21T10:00:00Z"},
            {"uuid": "dev-b", "lastSyncTime": "2026-05-21T11:00:00Z"},
        ],
        "nextPageToken": None,
    }
    devices_run2 = {
        "devices": [
            {"uuid": "dev-a", "lastSyncTime": "2026-05-21T10:00:00Z"},  # unchanged
            {"uuid": "dev-b", "lastSyncTime": "2026-05-21T11:00:00Z"},  # unchanged
            {"uuid": "dev-c", "lastSyncTime": "2026-05-22T09:00:00Z"},  # new
        ],
        "nextPageToken": None,
    }

    # Run 1 — no checkpoint
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/device_groups", json=sample_groups_response)
        m.get(f"{test_connector.base_url}/v1/devices", json=devices_run1)
        list(test_connector.get_assets())
        test_connector.update_checkpoint()

    assert test_connector.most_recent_date_seen is not None

    # Run 2 — checkpoint set from run 1
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/device_groups", json=sample_groups_response)
        m.get(f"{test_connector.base_url}/v1/devices", json=devices_run2)
        assets_run2 = list(test_connector.get_assets())

    uuids_run2 = [a.device.uid for a in assets_run2]
    assert "dev-c" in uuids_run2  # new device → included
    assert "dev-a" not in uuids_run2  # unchanged since run 1 → skipped
    assert "dev-b" not in uuids_run2  # unchanged since run 1 → skipped
