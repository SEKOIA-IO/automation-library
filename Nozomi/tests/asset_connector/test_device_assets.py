import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests_mock

from nozomi_networks import NozomiConfiguration, NozomiModule
from nozomi_networks.asset_connector.client import NozomiQueryClient, NozomiQueryError
from nozomi_networks.asset_connector.device_assets import NozomiDeviceAssetConnector
from nozomi_networks.asset_connector.models import NozomiAsset
from sekoia_automation.asset_connector.models.ocsf.device import (
    DeviceOCSFModel,
    DeviceTypeId,
    DeviceTypeStr,
)


BASE_URL = "https://guardian.test"
SIGN_IN_URL = f"{BASE_URL}/api/open/sign_in"
QUERY_URL = f"{BASE_URL}/api/open/query/do"


@pytest.fixture
def sample_assets() -> list[dict]:
    return [
        {
            "name": "AC 800M PM851",
            "id": "9e917f4e-e542-4e25-9715-74883145c532",
            "ip": ["192.168.196.234"],
            "mac_address": ["00:00:23:18:28:42"],
            "mac_vendor": ["ABB"],
            "os": "",
            "roles": ["producer"],
            "vendor": "ABB",
            "firmware_version": "5.1.100.13",
            "product_name": "AC 800M PM851",
            "serial_number": "",
            "type": "controller",
            "protocols": ["cotp", "mms"],
            "zones": ["Production_B"],
            "levels": ["2"],
            "created_at": "1724888822710",
            "last_activity_time": "1789542303500",
            "device_id": "d648bf95-cdd8-4985-a4ab-631ea594fccb",
        },
        {
            "name": "IEC61850.local",
            "id": "dbcc4903-65b8-4703-b1e5-29eb2312c4ce",
            "ip": ["10.41.132.164", "fe80::4eb:628b:8423:2816"],
            "mac_address": ["d0:03:4b:18:9e:41"],
            "mac_vendor": ["Apple"],
            "os": "tvOS",
            "roles": ["other"],
            "vendor": "Apple",
            "firmware_version": "",
            "product_name": "Apple TV HD (4th Generation)",
            "type": "audio_video",
            "protocols": ["mdns"],
            "zones": ["Undefined"],
            "created_at": "1724888832629",
            "last_activity_time": "1789542241632",
            "device_id": "d0:03:4b:18:9e:41",
        },
    ]


@pytest.fixture
def test_connector(symphony_storage):
    module = NozomiModule()
    module.configuration = NozomiConfiguration(
        key_name="fake_key_name",
        key_token="fake_key_token",
        base_url=BASE_URL,
    )

    connector = NozomiDeviceAssetConnector(module=module, data_path=symphony_storage)
    connector.configuration = {
        "sekoia_base_url": "https://sekoia.io",
        "sekoia_api_key": "fake_api_key",
        "frequency": 60,
    }

    connector.log = Mock()
    connector.log_exception = Mock()

    yield connector


# --- Model / builder tests ---


def test_build_device_type_mapping(test_connector):
    assert test_connector.build_device_type("server") == (DeviceTypeStr.SERVER, DeviceTypeId.SERVER)
    assert test_connector.build_device_type("Workstation") == (DeviceTypeStr.DESKTOP, DeviceTypeId.DESKTOP)
    assert test_connector.build_device_type("controller") == (DeviceTypeStr.OTHER, DeviceTypeId.OTHER)
    assert test_connector.build_device_type(None) == (DeviceTypeStr.UNKNOWN, DeviceTypeId.UNKNOWN)


def test_extract_os_type(test_connector):
    assert test_connector.extract_os_type(None) == "UNKNOWN"
    assert test_connector.extract_os_type("") == "UNKNOWN"
    assert test_connector.extract_os_type("windows") == "WINDOWS"
    assert test_connector.extract_os_type("tvOS") == "OTHER"


def test_parse_epoch_ms(test_connector):
    dt = test_connector._parse_epoch_ms("1724888822710")
    assert dt is not None
    assert abs(dt.timestamp() - 1724888822.710) < 0.001
    assert test_connector._parse_epoch_ms("0") is None
    assert test_connector._parse_epoch_ms(None) is None
    assert test_connector._parse_epoch_ms("not-a-number") is None


def test_build_operating_system_empty_returns_none(test_connector, sample_assets):
    asset = NozomiAsset.parse_obj(sample_assets[0])
    assert test_connector.build_operating_system(asset) is None


def test_build_operating_system_other(test_connector, sample_assets):
    asset = NozomiAsset.parse_obj(sample_assets[1])
    os = test_connector.build_operating_system(asset)
    assert os is not None
    assert os.name == "tvOS"
    assert os.type_id.value == 99


def test_build_network_interfaces(test_connector, sample_assets):
    asset = NozomiAsset.parse_obj(sample_assets[1])
    interfaces = test_connector.build_network_interfaces(asset)
    assert interfaces is not None
    assert len(interfaces) == 2
    assert all(iface.mac == "d0:03:4b:18:9e:41" for iface in interfaces)


def test_build_device(test_connector, sample_assets):
    asset = NozomiAsset.parse_obj(sample_assets[0])
    device = test_connector.build_device(asset)
    assert device.uid == asset.id
    assert device.hostname == "AC 800M PM851"
    assert device.ip == "192.168.196.234"
    assert device.vendor_name == "ABB"
    assert device.model == "AC 800M PM851"
    assert device.type_id == DeviceTypeId.OTHER
    assert abs(device.created_time - 1724888822.710) < 0.001


def test_build_device_hostname_fallback(test_connector):
    asset = NozomiAsset(id="abc", name=None)
    device = test_connector.build_device(asset)
    assert device.hostname == "abc"


def test_build_enrichments(test_connector, sample_assets):
    asset = NozomiAsset.parse_obj(sample_assets[0])
    enrichments = test_connector.build_enrichments(asset)
    names = {e.name for e in enrichments}
    assert "firmware_version" in names
    assert "zones" in names
    assert "serial_number" not in names  # empty string is skipped


def test_map_fields_produces_ocsf(test_connector, sample_assets):
    asset = NozomiAsset.parse_obj(sample_assets[0])
    result = test_connector.map_fields(asset)
    assert isinstance(result, DeviceOCSFModel)
    assert result.class_uid == 5001
    assert result.type_uid == 500102
    assert result.activity_id == 2
    assert result.device.uid == asset.id
    assert result.metadata.product.name == "Nozomi Networks"


def test_map_fields_json_serializable(test_connector, sample_assets):
    asset = NozomiAsset.parse_obj(sample_assets[0])
    result = test_connector.map_fields(asset)
    data = result.model_dump(exclude_none=True)
    assert json.dumps(data)
    assert data["class_uid"] == 5001


# --- Client tests (requests_mock) ---


def test_client_fetch_assets_single_page(sample_assets):
    client = NozomiQueryClient("k", "t", BASE_URL, page_size=1000)
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, status_code=200, json={"access_token": "xyz", "token_type": "Bearer"})
        m.get(QUERY_URL, status_code=200, json={"result": sample_assets})
        pages = list(client.fetch_assets(None))
    assert len(pages) == 1
    assert len(pages[0]) == 2
    assert all(isinstance(a, NozomiAsset) for a in pages[0])


def test_client_fetch_assets_empty(sample_assets):
    client = NozomiQueryClient("k", "t", BASE_URL, page_size=1000)
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, status_code=200, json={"access_token": "xyz", "token_type": "Bearer"})
        m.get(QUERY_URL, status_code=200, json={"result": []})
        pages = list(client.fetch_assets(None))
    assert pages == []


def test_client_fetch_assets_pagination(sample_assets):
    client = NozomiQueryClient("k", "t", BASE_URL, page_size=2)
    first_page = sample_assets  # exactly page_size -> continue
    second_page = [sample_assets[0]]  # < page_size -> stop
    responses = [
        {"json": {"result": first_page}, "status_code": 200},
        {"json": {"result": second_page}, "status_code": 200},
    ]
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, status_code=200, json={"access_token": "xyz", "token_type": "Bearer"})
        m.get(QUERY_URL, responses)
        pages = list(client.fetch_assets(None))
    assert len(pages) == 2
    assert len(pages[0]) == 2
    assert len(pages[1]) == 1


def test_client_reauth_on_401(sample_assets):
    client = NozomiQueryClient("k", "t", BASE_URL, page_size=1000)
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, status_code=200, json={"access_token": "xyz", "token_type": "Bearer"})
        m.get(
            QUERY_URL,
            [
                {"status_code": 401, "text": "expired"},
                {"status_code": 200, "json": {"result": sample_assets}},
            ],
        )
        pages = list(client.fetch_assets(None))
    assert len(pages) == 1


def test_client_sign_in_failure():
    client = NozomiQueryClient("k", "t", BASE_URL)
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, status_code=403, text="forbidden")
        with pytest.raises(NozomiQueryError):
            list(client.fetch_assets(None))


def test_build_assets_query():
    client = NozomiQueryClient("k", "t", BASE_URL, page_size=500)
    q = client.build_assets_query(1724888822710, 0, 500)
    assert "assets" in q
    assert "where created_at > 1724888822710" in q
    assert "sort created_at asc" in q
    assert "head 500" in q
    assert "skip" not in q

    q2 = client.build_assets_query(None, 500, 500)
    assert "where" not in q2
    assert "skip 500" in q2


# --- get_assets integration ---


def test_get_assets_yields_models(test_connector, sample_assets):
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, status_code=200, json={"access_token": "xyz", "token_type": "Bearer"})
        m.get(QUERY_URL, status_code=200, json={"result": sample_assets})

        with patch.object(
            type(test_connector),
            "most_recent_date_seen",
            new_callable=lambda: property(lambda self: None),
        ):
            assets = list(test_connector.get_assets())

    assert len(assets) == 2
    assert all(isinstance(a, DeviceOCSFModel) for a in assets)


def test_get_assets_updates_checkpoint(test_connector, sample_assets):
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, status_code=200, json={"access_token": "xyz", "token_type": "Bearer"})
        m.get(QUERY_URL, status_code=200, json={"result": sample_assets})

        with patch.object(
            type(test_connector),
            "most_recent_date_seen",
            new_callable=lambda: property(lambda self: None),
        ):
            list(test_connector.get_assets())

        test_connector.update_checkpoint()

    with test_connector.context as cache:
        assert cache.get("most_recent_date_seen") is not None
