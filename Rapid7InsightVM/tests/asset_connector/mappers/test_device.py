import pytest

from rapid7_insightvm.asset_connector.mappers import DeviceMapper
from rapid7_insightvm.asset_connector.models import Rapid7Asset
from tests.asset_connector.builders import ASSET_ID, asset


def test_device():
    device = DeviceMapper(asset()).map()

    assert device.model_dump(mode="json", exclude_none=True) == {
        "uid": ASSET_ID,
        "hostname": "host-01.example.com",
        "type": "Virtual",
        "type_id": 6,
    }


def test_device_minimal():
    device = DeviceMapper(Rapid7Asset.model_validate({"id": ASSET_ID, "type": None})).map()
    assert device.model_dump(mode="json", exclude_none=True) == {
        "uid": ASSET_ID,
        "hostname": ASSET_ID,
        "type": "Unknown",
        "type_id": 0,
    }


def test_device_hostname_falls_back_to_the_ip():
    assert DeviceMapper(asset(host_name=None)).map().hostname == "192.0.2.10"


@pytest.mark.parametrize(
    "asset_type, expected",
    [
        ("guest", ("Virtual", 6)),
        ("Guest", ("Virtual", 6)),
        ("hypervisor", ("Server", 1)),
        ("mobile", ("Mobile", 5)),
        ("physical", ("Unknown", 0)),
        ("unknown", ("Unknown", 0)),
        (None, ("Unknown", 0)),
    ],
)
def test_device_type(asset_type, expected):
    device = DeviceMapper(asset(type=asset_type)).map()
    assert (device.type, device.type_id) == expected
