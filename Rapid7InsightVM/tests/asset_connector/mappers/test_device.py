import pytest

from rapid7_insightvm.asset_connector.mappers import DeviceMapper
from rapid7_insightvm.asset_connector.mappers.device import pick_hostname
from rapid7_insightvm.asset_connector.models import Rapid7Asset
from tests.asset_connector.builders import ASSET_ID, asset


def test_device():
    device = DeviceMapper(asset()).map()

    assert device.model_dump(mode="json", exclude_none=True) == {
        "uid": ASSET_ID,
        "hostname": "host-01",
        "domain": "example.com",
        "ip": "192.0.2.10",
        "type": "Virtual",
        "type_id": 6,
    }


def test_device_minimal():
    device = DeviceMapper(Rapid7Asset.model_validate({"id": ASSET_ID, "host_name": "HOST-01", "type": None})).map()
    assert device.model_dump(mode="json", exclude_none=True) == {
        "uid": ASSET_ID,
        "hostname": "host-01",
        "type": "Unknown",
        "type_id": 0,
    }


@pytest.mark.parametrize(
    "host_name, expected",
    [
        # FQDN: short name + domain
        ("srv-01.corp.example.com", ("srv-01", "corp.example.com")),
        # short name
        ("SRV-01", ("srv-01", None)),
        # no public suffix: kept whole
        ("srv-01.local", ("srv-01.local", None)),
    ],
)
def test_device_hostname_and_domain(host_name, expected):
    device = DeviceMapper(asset(host_name=host_name)).map()
    assert (device.hostname, device.domain) == expected
    assert device.ip == "192.0.2.10"


@pytest.mark.parametrize("host_name", [None, "", "192.0.2.10", "2001:db8::1", "12345"])
def test_device_without_usable_hostname_is_refused(host_name):
    """D6: never the IP address nor the asset id as hostname."""
    with pytest.raises(ValueError, match="no usable hostname"):
        DeviceMapper(asset(host_name=host_name)).map()


def test_pick_hostname_takes_the_first_usable_candidate():
    assert pick_hostname(None, "192.0.2.10", "srv-01.example.com") == ("srv-01", "example.com")


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
