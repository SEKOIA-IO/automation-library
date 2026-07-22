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
from holm_security.asset_connector.models import HolmDevice

BASE_URL = "https://se-api.holmsecurity.com"
DEVICES_URL = f"{BASE_URL}/v2/devices"


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
