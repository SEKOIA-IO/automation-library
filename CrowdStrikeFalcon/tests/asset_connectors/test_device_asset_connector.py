from unittest.mock import Mock

import pytest
from requests.exceptions import HTTPError
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.device import (
    DeviceTypeId,
    DeviceTypeStr,
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.asset_connector.models.ocsf.group import Group

from crowdstrike_falcon.asset_connectors.crowdstrike_device_model import CrowdStrikeDevice, PolicyEntry
from crowdstrike_falcon.asset_connectors import rate_limit
from crowdstrike_falcon.asset_connectors.device_assets import CrowdstrikeDeviceAssetConnector
from sekoia_automation.exceptions import AssetConnectorRateLimitError


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
            CrowdStrikeDevice(platform_name="Windows", os_version="Windows 11 Pro"),
            "Windows 11 Pro",
            OSTypeStr.WINDOWS,
            OSTypeId.WINDOWS,
        ),
        (
            CrowdStrikeDevice(platform_name="Linux", os_version="Ubuntu 22.04"),
            "Ubuntu 22.04",
            OSTypeStr.LINUX,
            OSTypeId.LINUX,
        ),
        (
            CrowdStrikeDevice(platform_name="Mac", os_version="macOS Ventura"),
            "macOS Ventura",
            OSTypeStr.MACOS,
            OSTypeId.MACOS,
        ),
        (
            CrowdStrikeDevice(platform_name="macOS", os_version="macOS Sonoma"),
            "macOS Sonoma",
            OSTypeStr.MACOS,
            OSTypeId.MACOS,
        ),
        (CrowdStrikeDevice(platform_name="iOS", os_version="iOS 17"), "iOS 17", OSTypeStr.IOS, OSTypeId.IOS),
        (
            CrowdStrikeDevice(platform_name="Android", os_version="Android 14"),
            "Android 14",
            OSTypeStr.ANDROID,
            OSTypeId.ANDROID,
        ),
        (CrowdStrikeDevice(platform_name="Windows"), "Windows", OSTypeStr.WINDOWS, OSTypeId.WINDOWS),
        (
            CrowdStrikeDevice(platform_name="CustomOS", os_version="CustomOS 1.0"),
            "CustomOS 1.0",
            OSTypeStr.UNKNOWN,
            OSTypeId.UNKNOWN,
        ),
        (CrowdStrikeDevice(os_version="Unknown OS"), "Unknown OS", OSTypeStr.UNKNOWN, OSTypeId.UNKNOWN),
        (CrowdStrikeDevice(), "Unknown", OSTypeStr.UNKNOWN, OSTypeId.UNKNOWN),
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
        (CrowdStrikeDevice(product_type_desc="Desktop"), DeviceTypeId.DESKTOP, DeviceTypeStr.DESKTOP),
        (CrowdStrikeDevice(product_type_desc="Workstation"), DeviceTypeId.DESKTOP, DeviceTypeStr.DESKTOP),
        (CrowdStrikeDevice(product_type_desc="Laptop"), DeviceTypeId.DESKTOP, DeviceTypeStr.DESKTOP),
        (CrowdStrikeDevice(product_type_desc="Server"), DeviceTypeId.SERVER, DeviceTypeStr.SERVER),
        (CrowdStrikeDevice(product_type_desc="Mobile"), DeviceTypeId.MOBILE, DeviceTypeStr.MOBILE),
        (CrowdStrikeDevice(product_type_desc="Phone"), DeviceTypeId.MOBILE, DeviceTypeStr.MOBILE),
        (CrowdStrikeDevice(product_type_desc="Tablet"), DeviceTypeId.MOBILE, DeviceTypeStr.MOBILE),
        (CrowdStrikeDevice(product_type_desc="Virtual"), DeviceTypeId.VIRTUAL, DeviceTypeStr.VIRTUAL),
        (CrowdStrikeDevice(product_type_desc="Appliance"), DeviceTypeId.UNKNOWN, DeviceTypeStr.UNKNOWN),
        (CrowdStrikeDevice(product_type_desc=""), DeviceTypeId.UNKNOWN, DeviceTypeStr.UNKNOWN),
        (CrowdStrikeDevice(), DeviceTypeId.UNKNOWN, DeviceTypeStr.UNKNOWN),
    ],
)
def test_device_type_mapping(device_data, expected_type_id, expected_type_str, connector):
    type_id, type_str = connector.get_device_type(device_data)
    assert type_id == expected_type_id
    assert type_str == expected_type_str


def test_get_firewall_status_enabled(connector):
    device = CrowdStrikeDevice(device_policies={"firewall": PolicyEntry(applied=True)})
    status = connector.get_firewall_status(device)
    assert status == "Enabled"


def test_get_firewall_status_disabled(connector):
    device = CrowdStrikeDevice(device_policies={"firewall": PolicyEntry(applied=False)})
    status = connector.get_firewall_status(device)
    assert status == "Disabled"


def test_get_firewall_status_missing(connector):
    device = CrowdStrikeDevice()
    status = connector.get_firewall_status(device)
    assert status == "Disabled"


def test_map_device_fields_firewall_enabled(connector):
    device = CrowdStrikeDevice(
        device_id="dev1",
        hostname="host1",
        platform_name="Windows",
        os_version="Windows 10",
        product_type_desc="Desktop",
        device_policies={"firewall": PolicyEntry(applied=True)},
    )
    model = connector.map_device_fields(device)
    assert model.device.uid == "dev1"
    assert model.device.os.type_id == OSTypeId.WINDOWS
    assert model.device.type_id == DeviceTypeId.DESKTOP
    assert model.enrichments[0].data.Firewall_status == "Enabled"


def test_map_device_fields_firewall_disabled_and_unknown_type(connector):
    device = CrowdStrikeDevice(
        device_id="dev2",
        hostname="host2",
        platform_name="AlienOS",
        product_type_desc="Blender",
        device_policies={"firewall": PolicyEntry(applied=False)},
    )
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
    assert [d.device_id for d in collected] == ["u5", "u4"]
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
    assert [d.device_id for d in collected] == ["u5", "u4", "u3"]
    assert client.get_devices_infos.call_count == 2
    client.get_devices_infos.assert_any_call(["u5", "u4"])
    client.get_devices_infos.assert_any_call(["u3"])
    assert connector._latest_id == "u5"


def test_get_assets_yields_mapped_models(monkeypatch, connector):
    sample_devices = [
        CrowdStrikeDevice(
            device_id="d1",
            hostname="h1",
            platform_name="Linux",
            product_type_desc="Server",
            device_policies={"firewall": PolicyEntry(applied=True)},
        ),
        CrowdStrikeDevice(
            device_id="d2",
            hostname="h2",
            platform_name="Mac",
            product_type_desc="Laptop",
            device_policies={"firewall": PolicyEntry(applied=False)},
        ),
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
    device = CrowdStrikeDevice(
        local_ip="192.168.1.10",
        mac_address="00-1a-2b-3c-4d-5e",
        hostname="host1",
        connection_ip="10.0.0.1",
    )
    interfaces = connector.get_network_interfaces(device)
    assert len(interfaces) == 2
    assert interfaces[0].ip == "192.168.1.10"
    assert interfaces[0].mac == "00:1A:2B:3C:4D:5E"


def test_get_organization(connector):
    device = CrowdStrikeDevice(cid="org-123", service_provider="Acme Corp")
    org = connector.get_organization(device)
    assert org.uid == "org-123"
    assert org.name == "Acme Corp"


def test_get_organization_missing_cid(connector):
    device = CrowdStrikeDevice(service_provider="Acme Corp")
    assert connector.get_organization(device) is None


def test_get_groups(connector):
    device = CrowdStrikeDevice(groups=["group1", "group2"])

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
    device = CrowdStrikeDevice(groups=["group1"])

    mock_client = Mock()
    mock_client.get_host_groups.side_effect = Exception("API error")
    connector.client = mock_client

    groups = connector.get_groups(device)

    assert len(groups) == 1
    assert groups[0].uid == "group1"
    assert groups[0].name == "group1"  # Fallback


def test_is_device_compliant(connector):
    compliant = CrowdStrikeDevice(
        status="normal", reduced_functionality_mode="no", filesystem_containment_status="normal"
    )
    non_compliant = CrowdStrikeDevice(
        status="contained",
        reduced_functionality_mode="yes",
        filesystem_containment_status="contained",
    )

    assert connector.is_device_compliant(compliant) is True
    assert connector.is_device_compliant(non_compliant) is False
    assert connector.is_device_compliant(CrowdStrikeDevice()) is None


def test_get_groups_reuses_cached_group_details(connector):
    mock_client = Mock()
    mock_client.get_host_groups.return_value = [{"id": "group1", "name": "Group One"}]
    connector.client = mock_client

    first = connector.get_groups(CrowdStrikeDevice(groups=["group1"]))
    second = connector.get_groups(CrowdStrikeDevice(groups=["group1"]))

    assert mock_client.get_host_groups.call_count == 1
    assert first[0].name == "Group One"
    assert second[0].name == "Group One"


def test_get_groups_logs_a_single_warning_when_the_group_api_is_forbidden(connector):
    mock_client = Mock()
    mock_client.get_host_groups.side_effect = HTTPError(
        "403 Client Error: Forbidden for url: "
        "https://api.eu-1.crowdstrike.com/devices/entities/host-groups/v1?ids=group1"
    )
    connector.client = mock_client

    first = connector.get_groups(CrowdStrikeDevice(groups=["group1"]))
    second = connector.get_groups(CrowdStrikeDevice(groups=["group2"]))

    assert mock_client.get_host_groups.call_count == 1
    assert first[0].name == "group1"
    assert second[0].name == "group2"

    warnings = [call for call in connector.log.call_args_list if call.kwargs.get("level") == "warning"]
    assert len(warnings) == 1


def test_next_devices_fetches_the_group_details_of_a_batch_in_a_single_request(connector):
    mock_client = Mock()
    mock_client.list_devices_uuids.return_value = ["dev-1", "dev-2"]
    mock_client.get_devices_infos.return_value = [
        {"device_id": "dev-1", "hostname": "host-1", "groups": ["group1"]},
        {"device_id": "dev-2", "hostname": "host-2", "groups": ["group1", "group2"]},
    ]
    mock_client.get_host_groups.return_value = [
        {"id": "group1", "name": "Group One"},
        {"id": "group2", "name": "Group Two"},
    ]
    connector.client = mock_client

    devices = list(connector.next_devices())

    assert len(devices) == 2
    assert mock_client.get_host_groups.call_count == 1
    assert mock_client.get_host_groups.call_args[0][0] == ["group1", "group2"]
    assert [group.name for group in connector.get_groups(devices[1])] == ["Group One", "Group Two"]


def test_get_assets_resets_the_group_state_between_cycles(connector):
    mock_client = Mock()
    mock_client.list_devices_uuids.return_value = []
    connector.client = mock_client
    connector._groups_cache = {"group1": Group(uid="group1", name="Group One")}
    connector._groups_fetch_disabled = True

    list(connector.get_assets())

    assert connector._groups_cache == {}
    assert connector._groups_fetch_disabled is False


def test_next_devices_does_not_checkpoint_before_the_walk_completes(connector):
    """Regression: an interrupted run must not commit a checkpoint (SekoiaLab/integration#1846).

    The SDK calls update_checkpoint() after every batch it pushes, so a checkpoint set
    at the start of the walk makes the next cycle skip every device the interrupted run
    never reached.
    """
    connector.LIMIT = 2
    client = Mock()
    client.list_devices_uuids.return_value = iter(["u5", "u4", "u3", "u2"])
    client.get_devices_infos.side_effect = lambda batch: [{"device_id": b} for b in batch]
    connector.client = client

    devices = connector.next_devices()
    # Consume the first batch only, as an interrupted cycle would
    next(devices)
    connector.update_checkpoint()

    assert connector._latest_id is None
    assert "most_recent_device_id" not in connector.context.store

    # Draining the generator completes the walk and releases the checkpoint
    list(devices)
    connector.update_checkpoint()
    assert connector.context.store["most_recent_device_id"] == "u5"


def test_next_devices_resumes_full_listing_after_an_interrupted_run(connector):
    uuids = ["u5", "u4", "u3", "u2"]
    connector.LIMIT = 2
    client = Mock()
    client.get_devices_infos.side_effect = lambda batch: [{"device_id": b} for b in batch]
    connector.client = client

    # Cycle 1 dies after the first batch
    client.list_devices_uuids.return_value = iter(uuids)
    devices = connector.next_devices()
    assert next(devices).device_id == "u5"
    devices.close()

    # Cycle 2 still sees the whole listing
    client.list_devices_uuids.return_value = iter(uuids)
    assert [d.device_id for d in connector.next_devices()] == uuids


def test_get_groups_resolves_each_group_once_across_devices(connector):
    mock_client = Mock()
    mock_client.get_host_groups.return_value = [{"id": "group1", "name": "Group One"}]
    connector.client = mock_client

    for _ in range(3):
        groups = connector.get_groups(CrowdStrikeDevice(groups=["group1"]))
        assert [g.name for g in groups] == ["Group One"]

    mock_client.get_host_groups.assert_called_once_with(["group1"])


def test_get_groups_only_looks_up_unknown_groups(connector):
    mock_client = Mock()
    mock_client.get_host_groups.side_effect = [
        [{"id": "group1", "name": "Group One"}],
        [{"id": "group2", "name": "Group Two"}],
    ]
    connector.client = mock_client

    connector.get_groups(CrowdStrikeDevice(groups=["group1"]))
    groups = connector.get_groups(CrowdStrikeDevice(groups=["group1", "group2"]))

    assert [g.name for g in groups] == ["Group One", "Group Two"]
    assert mock_client.get_host_groups.call_args_list[-1].args[0] == ["group2"]


def test_get_groups_caches_the_fallback_so_a_failing_lookup_is_not_retried(connector):
    mock_client = Mock()
    mock_client.get_host_groups.side_effect = Exception("403 Forbidden")
    connector.client = mock_client

    for _ in range(3):
        groups = connector.get_groups(CrowdStrikeDevice(groups=["group1"]))
        assert [(g.uid, g.name) for g in groups] == [("group1", "group1")]

    mock_client.get_host_groups.assert_called_once()


def test_get_assets_resets_the_group_cache_between_cycles(connector):
    connector._groups_cache = {"stale": Group(uid="stale", name="Stale")}
    client = Mock()
    client.list_devices_uuids.return_value = iter([])
    connector.client = client

    assert list(connector.get_assets()) == []
    assert connector._groups_cache == {}


def test_update_checkpoint_held_back_when_a_batch_was_dropped(connector):
    """A batch Sekoia refused was never ingested, so the run must be replayed."""
    connector._latest_id = "u5"
    connector._push_failed = True

    connector.update_checkpoint()

    assert "most_recent_device_id" not in connector.context.store


def test_post_assets_to_api_flags_a_dropped_batch(connector, monkeypatch):
    monkeypatch.setattr(AssetConnector, "post_assets_to_api", lambda *a, **kw: None)
    assert connector.post_assets_to_api(Mock(), "https://api.fake") is None
    assert connector._push_failed is True


def test_asset_fetch_cycle_commits_the_checkpoint_once_every_batch_is_pushed(connector, monkeypatch):
    def fake_cycle(self):
        self._latest_id = "u5"

    monkeypatch.setattr(AssetConnector, "asset_fetch_cycle", fake_cycle)

    connector.asset_fetch_cycle()

    assert connector.context.store["most_recent_device_id"] == "u5"


class _PersistentContext:
    """Behaves like PersistentJSON: survives across fetch cycles."""

    def __init__(self):
        self.store = {}

    def __enter__(self):
        return self.store

    def __exit__(self, *args):
        pass


def _install_push_session(connector, statuses):
    """Mock the Sekoia push; `statuses` gives the status code of each POST."""
    pushed = []
    codes = iter(statuses)

    def post(url, json=None, timeout=None):
        res = Mock()
        res.status_code = next(codes)
        res.headers = {}
        res.json.return_value = {}
        if res.status_code == 200:
            pushed.append(len(json["items"]))
        return res

    session = Mock()
    session.post.side_effect = post
    connector.__dict__["_http_session"] = session
    return pushed


def test_asset_fetch_cycle_replays_an_interrupted_backfill(connector, monkeypatch):
    """SekoiaLab/integration#1846: a run cut short must not strand the devices it missed."""
    total, batch = 200, 100
    connector.LIMIT = batch
    connector.configuration = {
        "sekoia_base_url": "https://api.fake.sekoia.io/",
        "sekoia_api_key": "fake_api_key",
        "batch_size": batch,
        "frequency": 0,
    }
    connector.module.connector_configuration_uuid = "adcd0095-0f3d-4699-8621-158977b6c2c3"
    connector.context = _PersistentContext()
    monkeypatch.setattr(connector, "_check_schema_and_reset_if_needed", lambda: None)
    monkeypatch.setattr(connector._stop_event, "wait", Mock(return_value=False))

    uuids = [f"dev-{i:03d}" for i in range(total)]  # first_seen.desc
    client = Mock()
    client.get_devices_infos.side_effect = lambda ids: [
        {"device_id": u, "hostname": f"host-{u}", "platform_name": "Windows"} for u in ids
    ]
    connector.client = client

    # Cycle 1: the second batch is refused, so nothing may be checkpointed
    client.list_devices_uuids.return_value = iter(uuids)
    pushed = _install_push_session(connector, [200, 500])
    connector.asset_fetch_cycle()

    assert pushed == [batch]
    assert "most_recent_device_id" not in connector.context.store

    # Cycle 2: the whole listing is walked again, no device is lost
    client.list_devices_uuids.return_value = iter(uuids)
    pushed = _install_push_session(connector, [200] * 5)
    connector.asset_fetch_cycle()

    assert sum(pushed) == total
    assert connector.context.store["most_recent_device_id"] == "dev-000"

    # Cycle 3: everything is collected, the checkpoint short-circuits the run
    client.list_devices_uuids.return_value = iter(uuids)
    pushed = _install_push_session(connector, [200] * 5)
    connector.asset_fetch_cycle()

    assert pushed == []


def _cycle_connector(connector, monkeypatch, total, batch=100):
    """Prepare a connector to run whole fetch cycles over `total` devices."""
    connector.LIMIT = batch
    connector.configuration = {
        "sekoia_base_url": "https://api.fake.sekoia.io/",
        "sekoia_api_key": "fake_api_key",
        "batch_size": batch,
        "frequency": 0,
    }
    connector.module.connector_configuration_uuid = "adcd0095-0f3d-4699-8621-158977b6c2c3"
    connector.context = _PersistentContext()
    monkeypatch.setattr(connector, "_check_schema_and_reset_if_needed", lambda: None)

    uuids = [f"dev-{i:03d}" for i in range(total)]  # first_seen.desc
    client = Mock()
    client.get_devices_infos.side_effect = lambda ids: [
        {"device_id": u, "hostname": f"host-{u}", "platform_name": "Windows"} for u in ids
    ]
    client.list_devices_uuids.side_effect = lambda **kwargs: iter(uuids)
    connector.client = client

    waits = Mock(return_value=False)
    monkeypatch.setattr(connector._stop_event, "wait", waits)
    return waits


def test_asset_fetch_cycle_retries_a_rate_limited_push(connector, monkeypatch):
    """SekoiaLab/integration#2073: a 429 must not make the connector re-push its inventory forever."""
    waits = _cycle_connector(connector, monkeypatch, total=300)

    pushed = _install_push_session(connector, [200, 429, 200, 200])
    connector.asset_fetch_cycle()

    assert sum(pushed) == 300
    assert connector.context.store["most_recent_device_id"] == "dev-000"
    rate_limit_waits = [c.args[0] for c in waits.call_args_list if c.args[0] > 1]
    assert rate_limit_waits == [60.0]

    # The next cycle has nothing new to push
    pushed = _install_push_session(connector, [200] * 5)
    connector.asset_fetch_cycle()
    assert pushed == []


def test_asset_fetch_cycle_gives_up_on_a_persistent_rate_limit(connector, monkeypatch):
    waits = _cycle_connector(connector, monkeypatch, total=300)
    connector.context.store["most_recent_device_id"] = "dev-200"
    attempts = connector.MAX_RATE_LIMIT_RETRIES + 1
    _install_push_session(connector, [429] * attempts)

    with pytest.raises(AssetConnectorRateLimitError):
        connector.asset_fetch_cycle()

    assert connector._http_session.post.call_count == attempts
    assert [c.args[0] for c in waits.call_args_list if c.args[0] > 1] == [60.0] * connector.MAX_RATE_LIMIT_RETRIES
    assert connector.context.store["most_recent_device_id"] == "dev-200"


def test_asset_fetch_cycle_stopped_while_waiting_for_the_rate_limit(connector, monkeypatch):
    waits = _cycle_connector(connector, monkeypatch, total=300)

    def stop_on_rate_limit_wait(delay):
        if delay > 1:
            connector._stop_event.set()
        return connector._stop_event.is_set()

    waits.side_effect = stop_on_rate_limit_wait
    pushed = _install_push_session(connector, [200, 429])

    connector.asset_fetch_cycle()

    assert pushed == [100]
    assert connector._http_session.post.call_count == 2
    assert connector._push_failed is True
    assert connector._latest_id is None
    assert "most_recent_device_id" not in connector.context.store


def test_post_assets_to_api_returns_none_when_stopped_during_the_rate_limit_wait(connector, monkeypatch):
    def rate_limited(*args, **kwargs):
        raise AssetConnectorRateLimitError(retry_after=3600)

    monkeypatch.setattr(AssetConnector, "post_assets_to_api", rate_limited)
    monkeypatch.setattr(connector._stop_event, "wait", lambda delay: connector._stop_event.set())

    assert connector.post_assets_to_api(assets=Mock(), asset_connector_api_url="https://api.fake") is None
    assert connector._push_failed is True


class _FakeClock:
    """Stands for `time` in the rate_limit module: only advances when the connector waits."""

    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now

    def wait(self, delay):
        self.now += delay
        return False


def test_asset_pushes_are_paced(connector, monkeypatch):
    _cycle_connector(connector, monkeypatch, total=300)
    clock = _FakeClock()
    monkeypatch.setattr(rate_limit, "time", clock)
    monkeypatch.setattr(connector._stop_event, "wait", clock.wait)

    push_times = []
    pushed = _install_push_session(connector, [200] * 3)
    post = connector._http_session.post.side_effect

    def timed_post(*args, **kwargs):
        push_times.append(clock.now)
        return post(*args, **kwargs)

    connector._http_session.post.side_effect = timed_post

    connector.asset_fetch_cycle()

    assert pushed == [100, 100, 100]
    intervals = [later - earlier for earlier, later in zip(push_times, push_times[1:])]
    assert intervals == [connector.MIN_PUSH_INTERVAL] * 2


def test_next_devices_stops_walking_when_the_connector_is_stopped(connector):
    connector.LIMIT = 2
    client = Mock()
    client.list_devices_uuids.return_value = iter(["u5", "u4", "u3", "u2"])
    client.get_devices_infos.side_effect = lambda batch: [{"device_id": b} for b in batch]
    connector.client = client

    devices = connector.next_devices()
    assert next(devices).device_id == "u5"
    connector._stop_event.set()

    assert [d.device_id for d in devices] == ["u4"]
    client.get_devices_infos.assert_called_once_with(["u5", "u4"])
    assert connector._latest_id is None


def test_asset_fetch_cycle_resumes_from_a_1_25_20_checkpoint(connector, monkeypatch):
    _cycle_connector(connector, monkeypatch, total=300)
    # Checkpoint as stored by the version 1.25.20 of the connector
    connector.context.store.update({"most_recent_device_id": "dev-050"})

    pushed = _install_push_session(connector, [200] * 3)
    connector.asset_fetch_cycle()

    assert pushed == [50]
    pushed_ids = [item["device"]["uid"] for item in connector._http_session.post.call_args.kwargs["json"]["items"]]
    assert pushed_ids == [f"dev-{i:03d}" for i in range(50)]
    assert connector.context.store == {"most_recent_device_id": "dev-000"}


def test_get_mapped_fields(connector):
    fields = connector.get_mapped_fields()

    assert isinstance(fields, dict)
    assert fields
    assert all(isinstance(key, str) and isinstance(value, str) for key, value in fields.items())
    assert fields["device_id"] == "device.uid"


def test_reset_checkpoint(connector):
    connector._latest_id = "device-1"
    connector.update_checkpoint()
    assert connector.most_recent_device_id == "device-1"

    connector.reset_checkpoint()

    assert connector._latest_id is None
    assert connector.most_recent_device_id is None


def test_reset_checkpoint_only_pops_its_own_key(connector):
    connector.context.store.update({"most_recent_device_id": "device-1", "other_key": "kept"})

    connector.reset_checkpoint()

    assert connector.context.store == {"other_key": "kept"}
