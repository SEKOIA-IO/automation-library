from unittest.mock import Mock

import pytest
from dateutil.parser import isoparse
from sekoia_automation.asset_connector.models.ocsf.device import (
    DeviceOCSFModel,
    DeviceTypeId,
    DeviceTypeStr,
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.module import Module

from holm_security.asset_connector.device_assets import HolmSecurityDeviceAssetConnector
from holm_security.asset_connector.models import HolmDevice, HolmNetAsset

BASE_URL = "https://se-api.holmsecurity.com"
DEVICES_URL = f"{BASE_URL}/v2/devices"
NET_ASSETS_URL = f"{BASE_URL}/v2/net-assets"
NET_ASSET_UUID = "7ae54691-3698-4ef6-9e50-7d021ef444a0"


def make_device(**overrides) -> dict:
    device = {
        "uid": "0123456789abcdef0123456789abcdef",
        "device_name": "DESKTOP-EXAMPLE01",
        "hostname": "desktop-example01",
        "state": "active",
        "last_sync": "2026-07-01T20:30:36.712744Z",
        "created": "2026-07-01T20:30:36.629532Z",
        "os_is_server": False,
        "os_family": "windows",
        "os_name": "Microsoft Windows Server 2025 Datacenter",
        "network": {
            "ip_address": "192.0.2.10",
            "ip_address_v6": "2001:db8::10",
            "mac_address": "00:00:5E:00:53:00",
        },
    }
    device.update(overrides)
    return device


def make_net_asset(**overrides) -> dict:
    asset = {
        "uuid": NET_ASSET_UUID,
        "name": "host-example01.example.com",
        "hostname": "host-example01.example.com",
        "ip": "192.0.2.20",
        "ip_range": None,
        "type": "host",
        "operating_system": "Ubuntu 22.04",
        "details": "",
        "created": "2026-07-01T16:37:00.667844Z",
        "last_detected": "2026-07-03T08:47:33Z",
        "vulnerabilities_count": 231,
        "risk_score": 100,
        "severity": {"critical": 19, "high": 32, "medium": 26, "low": 5, "info": 70},
    }
    asset.update(overrides)
    return asset


def empty_page() -> dict:
    return {"count": 0, "next": None, "previous": None, "results": []}


@pytest.fixture(autouse=True)
def default_net_assets(requests_mock):
    """Most device tests only care about the agent inventory."""
    requests_mock.get(NET_ASSETS_URL, json=empty_page())


@pytest.fixture
def connector(symphony_storage):
    module = Module()
    module.configuration = {
        "base_url": BASE_URL,
        "api_token": "fake_api_token",
    }

    connector = HolmSecurityDeviceAssetConnector(module=module, data_path=symphony_storage)
    connector.configuration = {
        "sekoia_base_url": "https://sekoia.io",
        "sekoia_api_key": "fake_sekoia_api_key",
        "frequency": 60,
    }
    connector.log = Mock()
    connector.log_exception = Mock()
    yield connector


def test_build_device_type():
    assert HolmSecurityDeviceAssetConnector.build_device_type(True) == (DeviceTypeStr.SERVER, DeviceTypeId.SERVER)
    assert HolmSecurityDeviceAssetConnector.build_device_type(False) == (DeviceTypeStr.DESKTOP, DeviceTypeId.DESKTOP)
    assert HolmSecurityDeviceAssetConnector.build_device_type(None) == (DeviceTypeStr.UNKNOWN, DeviceTypeId.UNKNOWN)


def test_map_fields_desktop(connector):
    asset = connector.map_fields(HolmDevice.model_validate(make_device()))

    assert isinstance(asset, DeviceOCSFModel)
    assert asset.class_uid == 5001
    assert asset.type_uid == 500102
    assert asset.activity_id == 2
    assert asset.time == isoparse("2026-07-01T20:30:36.712744Z").timestamp()
    assert asset.metadata.product.name == "Holm Security"
    assert asset.metadata.product.version == "v2"
    assert asset.metadata.version == "1.5.0"

    device = asset.device
    assert device.uid == "0123456789abcdef0123456789abcdef"
    assert device.name == "DESKTOP-EXAMPLE01"
    assert device.hostname == "desktop-example01"
    assert device.type == DeviceTypeStr.DESKTOP
    assert device.type_id == DeviceTypeId.DESKTOP
    assert device.ip == "192.0.2.10"
    assert device.created_time == isoparse("2026-07-01T20:30:36.629532Z").timestamp()
    assert device.last_seen_time == isoparse("2026-07-01T20:30:36.712744Z").timestamp()


def test_map_fields_server(connector):
    asset = connector.map_fields(HolmDevice.model_validate(make_device(os_is_server=True)))
    assert asset.device.type == DeviceTypeStr.SERVER
    assert asset.device.type_id == DeviceTypeId.SERVER


def test_operating_system_windows(connector):
    device = connector.build_device(HolmDevice.model_validate(make_device()))
    assert device.os is not None
    assert device.os.name == "Microsoft Windows Server 2025 Datacenter"
    assert device.os.type == OSTypeStr.WINDOWS
    assert device.os.type_id == OSTypeId.WINDOWS


def test_operating_system_unknown_family(connector):
    device = connector.build_device(HolmDevice.model_validate(make_device(os_family="plan9")))
    assert device.os.type == OSTypeStr.OTHER
    assert device.os.type_id == OSTypeId.OTHER


def test_operating_system_absent(connector):
    device = connector.build_device(HolmDevice.model_validate(make_device(os_family=None, os_name=None)))
    assert device.os is None


def test_network_interfaces_ipv4_and_ipv6(connector):
    device = connector.build_device(HolmDevice.model_validate(make_device()))
    assert device.network_interfaces is not None
    assert len(device.network_interfaces) == 2

    ipv4 = device.network_interfaces[0]
    assert ipv4.ip == "192.0.2.10"
    assert ipv4.mac == "00:00:5E:00:53:00"
    assert ipv4.hostname == "desktop-example01"

    ipv6 = device.network_interfaces[1]
    assert ipv6.ip == "2001:db8::10"


def test_network_interfaces_ipv4_only(connector):
    payload = make_device()
    payload["network"] = {"ip_address": "10.0.0.1", "mac_address": None}
    device = connector.build_device(HolmDevice.model_validate(payload))
    assert len(device.network_interfaces) == 1
    assert device.network_interfaces[0].ip == "10.0.0.1"


def test_network_absent(connector):
    device = connector.build_device(HolmDevice.model_validate(make_device(network=None)))
    assert device.network_interfaces is None
    assert device.ip is None


def test_hostname_fallback(connector):
    device = connector.build_device(HolmDevice.model_validate(make_device(hostname=None)))
    assert device.hostname == ""


def test_map_fields_without_timestamps_raises(connector):
    with pytest.raises(ValueError):
        connector.map_fields(HolmDevice.model_validate(make_device(last_sync=None, created=None)))


def test_get_assets_paginates(connector, requests_mock):
    device_a = make_device(uid="aaa", last_sync="2026-07-01T10:00:00Z")
    device_b = make_device(uid="bbb", last_sync="2026-07-02T10:00:00Z")

    requests_mock.get(
        DEVICES_URL,
        json={"count": 2, "next": f"{DEVICES_URL}?offset=1&limit=1", "previous": None, "results": [device_a]},
    )
    requests_mock.get(
        f"{DEVICES_URL}?offset=1&limit=1",
        json={"count": 2, "next": None, "previous": None, "results": [device_b]},
    )

    assets = list(connector.get_assets())

    assert [asset.device.uid for asset in assets] == ["aaa", "bbb"]
    # Checkpoint advances to the most recent last_sync seen.
    assert connector._latest_time == "2026-07-02T10:00:00Z"


def test_get_assets_checkpoint_filter(connector, requests_mock):
    with connector.context as cache:
        cache["most_recent_last_sync"] = "2026-07-01T20:30:36.712744Z"

    old_device = make_device(uid="old", last_sync="2026-06-01T00:00:00Z")
    new_device = make_device(uid="new", last_sync="2026-07-10T00:00:00Z")

    requests_mock.get(
        DEVICES_URL,
        json={"count": 2, "next": None, "previous": None, "results": [old_device, new_device]},
    )

    assets = list(connector.get_assets())

    assert [asset.device.uid for asset in assets] == ["new"]
    assert connector._latest_time == "2026-07-10T00:00:00Z"


def test_update_checkpoint_persists(connector):
    connector._latest_time = "2026-07-10T00:00:00Z"
    connector.update_checkpoint()

    assert connector.most_recent_last_sync == "2026-07-10T00:00:00Z"


def test_update_checkpoint_noop_when_unset(connector):
    connector._latest_time = None
    connector.update_checkpoint()

    assert connector.most_recent_last_sync is None


def test_get_assets_skips_device_without_timestamp(connector, requests_mock):
    good = make_device(uid="good")
    bad = make_device(uid="bad", last_sync=None, created=None)

    requests_mock.get(DEVICES_URL, json={"count": 2, "next": None, "previous": None, "results": [good, bad]})

    assets = list(connector.get_assets())

    assert [asset.device.uid for asset in assets] == ["good"]


def test_get_assets_raises_on_api_error(connector, requests_mock):
    requests_mock.get(DEVICES_URL, json={"detail": "Server error"}, status_code=500)

    with pytest.raises(Exception):
        list(connector.get_assets())


def test_seen_device_ids_empty_by_default(connector):
    assert connector.seen_device_ids == set()


def test_get_assets_skips_already_cached_device(connector, requests_mock):
    """A device whose UID is in seen_device_ids must not be yielded."""
    with connector.context as cache:
        cache["seen_device_ids"] = ["0123456789abcdef0123456789abcdef"]

    requests_mock.get(
        DEVICES_URL,
        json={"count": 1, "next": None, "previous": None, "results": [make_device()]},
    )

    assets = list(connector.get_assets())

    assert assets == []


def test_get_assets_new_device_tracked_in_memory(connector, requests_mock):
    """A newly seen device UID is added to _new_device_ids before checkpoint is saved."""
    requests_mock.get(
        DEVICES_URL,
        json={"count": 1, "next": None, "previous": None, "results": [make_device()]},
    )

    list(connector.get_assets())

    assert "0123456789abcdef0123456789abcdef" in connector._new_device_ids


def test_update_checkpoint_persists_new_device_ids(connector):
    """update_checkpoint merges _new_device_ids into the context."""
    connector._new_device_ids = {"uid-aaa", "uid-bbb"}

    connector.update_checkpoint()

    assert connector.seen_device_ids == {"uid-aaa", "uid-bbb"}
    assert connector._new_device_ids == set()


def test_get_mapped_fields_declares_mapping(connector):
    fields = connector.get_mapped_fields()

    assert fields["uid"] == "device.uid"
    assert fields["hostname"] == "device.hostname"
    assert fields["os_family"] == "device.os.type"
    assert fields["last_sync"] == "device.last_seen_time"
    assert fields["max_severity"] == "device.risk_level"


def test_reset_checkpoint_clears_context(connector):
    connector._latest_time = "2026-07-01T20:30:36Z"
    connector._new_device_ids = {"uid-aaa"}
    connector.update_checkpoint()
    assert connector.most_recent_last_sync == "2026-07-01T20:30:36Z"
    assert connector.seen_device_ids == {"uid-aaa"}

    connector.reset_checkpoint()

    assert connector.most_recent_last_sync is None
    assert connector.seen_device_ids == set()
    assert connector._latest_time is None
    assert connector._new_device_ids == set()


def test_update_checkpoint_merges_with_existing_cached_ids(connector):
    """Existing cached IDs are kept when new ones are added."""
    with connector.context as cache:
        cache["seen_device_ids"] = ["uid-existing"]

    connector._new_device_ids = {"uid-new"}
    connector.update_checkpoint()

    assert connector.seen_device_ids == {"uid-existing", "uid-new"}


def test_get_assets_deduplication_across_cycles(connector, requests_mock):
    """Simulate two consecutive cycles: device pushed once, skipped on second cycle."""
    requests_mock.get(
        DEVICES_URL,
        json={"count": 1, "next": None, "previous": None, "results": [make_device()]},
    )

    # First cycle
    assets_cycle_1 = list(connector.get_assets())
    connector.update_checkpoint()

    # Second cycle
    assets_cycle_2 = list(connector.get_assets())

    assert len(assets_cycle_1) == 1
    assert len(assets_cycle_2) == 0


# --- scanned network assets -------------------------------------------------


def test_devices_pagination_uses_limit(connector, requests_mock):
    devices = requests_mock.get(DEVICES_URL, json=empty_page())

    list(connector.get_assets())

    # The Holm API paginates with `limit`/`offset` and silently ignores `page_size`.
    assert devices.last_request.qs.get("limit") == ["100"]
    assert devices.last_request.qs.get("page_size") is None


def test_map_net_asset_fields(connector):
    asset = connector.map_net_asset_fields(HolmNetAsset.model_validate(make_net_asset()))

    assert isinstance(asset, DeviceOCSFModel)
    assert asset.class_uid == 5001
    assert asset.time == isoparse("2026-07-03T08:47:33Z").timestamp()

    device = asset.device
    assert device.uid == NET_ASSET_UUID
    assert device.hostname == "host-example01.example.com"
    assert device.name == "host-example01.example.com"
    assert device.ip == "192.0.2.20"
    assert device.is_managed is False
    assert device.vendor_name is None
    assert device.risk_score == 100
    assert device.risk_level == "Critical"
    assert device.created_time == isoparse("2026-07-01T16:37:00.667844Z").timestamp()
    assert device.last_seen_time == isoparse("2026-07-03T08:47:33Z").timestamp()
    # A scan reports no MAC address, so no network interface is emitted.
    assert device.network_interfaces is None


def test_net_asset_device_type(connector):
    host = connector.build_net_asset_device(HolmNetAsset.model_validate(make_net_asset()))
    assert (host.type, host.type_id) == (DeviceTypeStr.UNKNOWN, DeviceTypeId.UNKNOWN)

    network = connector.build_net_asset_device(HolmNetAsset.model_validate(make_net_asset(type="network")))
    assert (network.type, network.type_id) == (DeviceTypeStr.OTHER, DeviceTypeId.OTHER)

    unknown = connector.build_net_asset_device(HolmNetAsset.model_validate(make_net_asset(type=None)))
    assert (unknown.type, unknown.type_id) == (DeviceTypeStr.UNKNOWN, DeviceTypeId.UNKNOWN)


def test_net_asset_operating_system_from_free_form_name(connector):
    linux = connector.build_net_asset_device(HolmNetAsset.model_validate(make_net_asset()))
    assert linux.os.name == "Ubuntu 22.04"
    assert linux.os.type == OSTypeStr.LINUX
    assert linux.os.type_id == OSTypeId.LINUX

    debian = connector.build_net_asset_device(
        HolmNetAsset.model_validate(make_net_asset(operating_system="Debian GNU/Linux 12"))
    )
    assert debian.os.type == OSTypeStr.LINUX

    exotic = connector.build_net_asset_device(HolmNetAsset.model_validate(make_net_asset(operating_system="Plan 9")))
    assert exotic.os.type == OSTypeStr.OTHER

    absent = connector.build_net_asset_device(HolmNetAsset.model_validate(make_net_asset(operating_system=None)))
    assert absent.os is None


def test_net_asset_risk_level_uses_the_most_severe_bucket(connector):
    high = connector.build_net_asset_device(
        HolmNetAsset.model_validate(
            make_net_asset(severity={"critical": 0, "high": 3, "medium": 0, "low": 0, "info": 9})
        )
    )
    assert high.risk_level == "High"

    empty = connector.build_net_asset_device(
        HolmNetAsset.model_validate(
            make_net_asset(severity={"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0})
        )
    )
    assert empty.risk_level is None


def test_map_net_asset_without_timestamps_raises(connector):
    with pytest.raises(ValueError):
        connector.map_net_asset_fields(HolmNetAsset.model_validate(make_net_asset(last_detected=None, created=None)))


def test_get_assets_yields_devices_then_net_assets(connector, requests_mock):
    requests_mock.get(DEVICES_URL, json={"count": 1, "next": None, "previous": None, "results": [make_device()]})
    requests_mock.get(
        NET_ASSETS_URL,
        json={"count": 1, "next": None, "previous": None, "results": [make_net_asset()]},
    )

    assets = list(connector.get_assets())

    assert [asset.device.uid for asset in assets] == ["0123456789abcdef0123456789abcdef", NET_ASSET_UUID]
    assert [asset.device.is_managed for asset in assets] == [True, False]


def test_net_assets_use_their_own_checkpoint(connector, requests_mock):
    with connector.context as cache:
        cache["most_recent_net_asset_last_detected"] = "2026-07-03T08:47:33Z"

    requests_mock.get(DEVICES_URL, json=empty_page())
    requests_mock.get(
        NET_ASSETS_URL,
        json={
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                make_net_asset(uuid="old-asset"),
                make_net_asset(uuid="new-asset", last_detected="2026-07-10T00:00:00Z"),
            ],
        },
    )

    assets = list(connector.get_assets())

    assert [asset.device.uid for asset in assets] == ["new-asset"]

    connector.update_checkpoint()
    assert connector.most_recent_net_asset_last_detected == "2026-07-10T00:00:00Z"
    assert connector.most_recent_last_sync is None


def test_reset_checkpoint_clears_the_net_asset_cursor(connector):
    connector._latest_net_asset_time = "2026-07-10T00:00:00Z"
    connector.update_checkpoint()
    assert connector.most_recent_net_asset_last_detected == "2026-07-10T00:00:00Z"

    connector.reset_checkpoint()

    assert connector.most_recent_net_asset_last_detected is None
    assert connector._latest_net_asset_time is None


def test_max_severity_accepts_the_integer_reported_by_the_api(connector):
    device = connector.build_device(HolmDevice.model_validate(make_device(max_severity=4)))
    assert device.risk_level == "Critical"

    named = connector.build_device(HolmDevice.model_validate(make_device(max_severity="high")))
    assert named.risk_level == "High"

    absent = connector.build_device(HolmDevice.model_validate(make_device(max_severity=None)))
    assert absent.risk_level is None


def test_get_mapped_fields_declares_the_net_asset_mapping(connector):
    fields = connector.get_mapped_fields()

    assert fields["net_assets.uuid"] == "device.uid"
    assert fields["net_assets.hostname"] == "device.hostname"
    assert fields["net_assets.last_detected"] == "device.last_seen_time"


def test_net_assets_api_failure_is_propagated(connector, requests_mock):
    requests_mock.get(DEVICES_URL, json=empty_page())
    requests_mock.get(NET_ASSETS_URL, json={"detail": "Server error"}, status_code=500)

    with pytest.raises(Exception):
        list(connector.get_assets())


def test_get_assets_skips_already_cached_net_asset(connector, requests_mock):
    with connector.context as cache:
        cache["seen_device_ids"] = [NET_ASSET_UUID]

    requests_mock.get(DEVICES_URL, json=empty_page())
    requests_mock.get(
        NET_ASSETS_URL,
        json={"count": 1, "next": None, "previous": None, "results": [make_net_asset()]},
    )

    assert list(connector.get_assets()) == []


def test_get_assets_skips_net_asset_without_timestamp(connector, requests_mock):
    requests_mock.get(DEVICES_URL, json=empty_page())
    requests_mock.get(
        NET_ASSETS_URL,
        json={
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                make_net_asset(uuid="bad", last_detected=None, created=None),
                make_net_asset(uuid="good"),
            ],
        },
    )

    assets = list(connector.get_assets())

    assert [asset.device.uid for asset in assets] == ["good"]


def test_net_asset_without_severity_has_no_risk_level(connector):
    device = connector.build_net_asset_device(HolmNetAsset.model_validate(make_net_asset(severity=None)))

    assert device.risk_level is None
    assert device.risk_level_id is None


def test_device_checkpoint_is_not_advanced_when_the_connector_stops(connector, requests_mock):
    """A run cut short may have left older devices unvisited."""

    def devices(request, context):
        connector.stop()
        return {"count": 2, "next": f"{DEVICES_URL}?offset=1&limit=1", "previous": None, "results": [make_device()]}

    requests_mock.get(DEVICES_URL, json=devices)

    assets = list(connector.get_assets())

    assert len(assets) == 1
    assert connector._latest_time is None

    connector.update_checkpoint()
    assert connector.most_recent_last_sync is None


def test_net_asset_checkpoint_is_not_advanced_when_the_connector_stops(connector, requests_mock):
    requests_mock.get(DEVICES_URL, json=empty_page())

    def net_assets(request, context):
        connector.stop()
        return {
            "count": 2,
            "next": f"{NET_ASSETS_URL}?offset=1&limit=1",
            "previous": None,
            "results": [make_net_asset()],
        }

    requests_mock.get(NET_ASSETS_URL, json=net_assets)

    assets = list(connector.get_assets())

    assert len(assets) == 1
    assert connector._latest_net_asset_time is None

    connector.update_checkpoint()
    assert connector.most_recent_net_asset_last_detected is None
