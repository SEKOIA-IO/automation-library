from unittest.mock import Mock, patch

import pytest
from sekoia_automation.asset_connector.models.ocsf.device import DeviceTypeId
from sekoia_automation.module import Module

from easyvista.asset_connector.device_assets import ASSET_FIELDS, KNOWN_DEVICES_KEY, EasyVistaDeviceAssetConnector
from easyvista.asset_connector.models import EasyVistaAsset

API_URL = "https://company.easyvista.com/api/v1/50004/assets"

# GET /assets record, based on the EasyVista documentation sample
SERVER = {
    "HREF": f"{API_URL}/9479",
    "ASSET_ID": "9479",
    "ASSET_LABEL": "Web server",
    "ASSET_TAG": "a99f7fc1-4080-402b-b85d-2c484c6108c7",
    "SERIAL_NUMBER": "2AS-155-6V",
    "NETWORK_IDENTIFIER": "SRV-WEB01.corp.example.com",
    "SERVER_TYPE_ID": "2",
    "DEPARTMENT_ID": "5",
    "DEPARTMENT_PATH": "IT/Infrastructure",
    "ENTRY_DATE": "2018-06-01",
    "INSTALLATION_DATE": "2018-07-03",
    "LAST_UPDATE": "2026-10-01T06:17:46.297-05:00",
    "LAST_AUTOMATIC_DISCOVERY": "2026-10-30T08:00:00.000+01:00",
    "REMOVED_DATE": "",
    "RECYCLED_DATE": "",
    "LOCATION": {"HREF": "", "CITY": "Paris", "LOCATION_PATH": "Europe/France/Paris", "LOCATION_ID": "66"},
    "DEPARTMENT": {"DEPARTMENT_ID": "5", "DEPARTMENT_PATH": "IT/Infrastructure"},
    "EMPLOYEE": {"E_MAIL": "jane.doe@example.com", "LAST_NAME": "Doe"},
    "CATALOG_ASSET": {"ARTICLE_MODEL": "PowerEdge 860", "SMBIOS_NAME": "PowerEdge 860", "CATALOG_ID": "3544"},
}

LAPTOP = {
    "ASSET_ID": "10370",
    "ASSET_LABEL": "",
    "ASSET_TAG": "TAG-10370",
    "SERIAL_NUMBER": " -",
    "NETWORK_IDENTIFIER": "LAPTOP42",
    "SERVER_TYPE_ID": "",
    "INSTALLATION_DATE": "",
    "LAST_UPDATE": "",
    "LOCATION": {"CITY": ""},
    "EMPLOYEE": {"E_MAIL": ""},
}

LICENSE = {"ASSET_ID": "20001", "ASSET_LABEL": "Office 365 E3", "NETWORK_IDENTIFIER": " -"}
REMOVED = {**LAPTOP, "ASSET_ID": "30001", "NETWORK_IDENTIFIER": "OLDPC", "REMOVED_DATE": "2025-01-31"}


def page(records, next_offset=None):
    payload = {"record_count": str(len(records)), "total_record_count": "999", "records": records}
    if next_offset is not None:
        payload["@next"] = f"{API_URL}?offset={next_offset}&max_rows=100"
    return {"json": payload}


@pytest.fixture
def connector(tmp_path):
    module = Module()
    module.configuration = {
        "base_url": "https://company.easyvista.com/",
        "account": "50004",
        "api_token": "token",
    }
    connector = EasyVistaDeviceAssetConnector(module=module, data_path=tmp_path)
    connector.configuration = {
        "sekoia_base_url": "https://api.sekoia.io",
        "sekoia_api_key": "api-key",
        "frequency": 86400,
        "batch_size": 1,
    }
    connector.log = Mock()
    connector.log_exception = Mock()
    return connector


def map_device(connector, record):
    return connector.map_fields(EasyVistaAsset.model_validate(record))


def test_map_server(connector):
    asset = map_device(connector, SERVER)
    device = asset.device

    assert device.uid == "9479"
    assert device.hostname == "srv-web01"
    assert device.domain == "corp.example.com"
    assert device.name == "SRV-WEB01.corp.example.com"
    assert device.desc == "Web server"
    assert device.type_id == DeviceTypeId.SERVER
    assert device.uid_alt == "2AS-155-6V"
    assert device.model == "PowerEdge 860"
    assert device.location.city == "Paris"
    assert device.groups[0].uid == "5"
    assert device.groups[0].name == "IT/Infrastructure"
    assert device.created_time == device.first_seen_time == 1530576000.0
    assert device.last_seen_time == 1793343600.0
    assert device.is_managed is True
    assert asset.time == 1790853466.297
    assert asset.metadata.product.name == "EasyVista Service Manager"
    assert asset.enrichments[0].data.Users == ["jane.doe@example.com"]
    assert asset.enrichments[0].data.Full_qualified_domain_name == "SRV-WEB01.corp.example.com"


def test_map_empty_values(connector):
    asset = map_device(connector, LAPTOP)
    device = asset.device

    assert device.hostname == "laptop42"
    assert device.domain is None
    assert device.type_id == DeviceTypeId.UNKNOWN
    assert device.uid_alt == "TAG-10370"
    assert device.desc is None
    assert device.model is None
    assert device.location is None
    assert device.groups is None
    assert device.created_time is None
    assert asset.enrichments is None
    assert asset.time > 0


def test_map_without_network_identifier(connector):
    assert map_device(connector, LICENSE) is None


def test_unparsable_date_is_dropped():
    asset = EasyVistaAsset.model_validate({**LAPTOP, "INSTALLATION_DATE": "03/07/2018"})
    assert asset.INSTALLATION_DATE is None


def test_get_assets_paginates_with_the_original_parameters(connector, requests_mock):
    mock = requests_mock.get(API_URL, [page([SERVER], next_offset=100), page([LAPTOP])])
    connector.configuration.search = "CATALOG_ID:3544"

    assets = list(connector.get_assets())

    assert [asset.device.uid for asset in assets] == ["9479", "10370"]
    first, second = mock.request_history
    assert first.headers["Authorization"] == "Bearer token"
    assert first.qs["fields"] == [",".join(ASSET_FIELDS).lower()]
    assert first.qs["search"] == ["catalog_id:3544"]
    assert first.qs["max_rows"] == ["100"]
    assert "offset" not in first.qs
    assert second.qs["offset"] == ["100"]
    assert second.qs["search"] == ["catalog_id:3544"]


def test_get_assets_stops_when_next_does_not_move(connector, requests_mock):
    requests_mock.get(API_URL, [page([SERVER], next_offset=100), page([LAPTOP], next_offset=100)])

    assert len(list(connector.get_assets())) == 2
    assert connector._listing_complete is True


def test_get_assets_skips_removed_licenses_and_invalid(connector, requests_mock):
    requests_mock.get(API_URL, **page([SERVER, LICENSE, REMOVED, {"ASSET_LABEL": "no id"}]))

    assert [asset.device.uid for asset in connector.get_assets()] == ["9479"]
    assert connector._skipped == {"removed": 1, "no_hostname": 1, "invalid": 1}


def test_get_assets_yields_only_new_or_changed_devices(connector, requests_mock):
    requests_mock.get(API_URL, **page([SERVER, LAPTOP]))
    assert len(list(connector.get_assets())) == 2
    connector.update_checkpoint()

    requests_mock.get(API_URL, **page([SERVER, {**LAPTOP, "ASSET_LABEL": "Renamed"}]))
    assert [asset.device.uid for asset in connector.get_assets()] == ["10370"]


def test_unchanged_cycle_drops_deleted_devices(connector, requests_mock):
    with connector.context as cache:
        cache[KNOWN_DEVICES_KEY] = {"deleted": "fingerprint"}
    requests_mock.get(API_URL, **page([SERVER]))
    list(connector.get_assets())
    connector.update_checkpoint()

    requests_mock.get(API_URL, **page([SERVER]))
    assert list(connector.get_assets()) == []

    with connector.context as cache:
        assert set(cache[KNOWN_DEVICES_KEY]) == {"9479"}


def test_api_error_keeps_known_devices(connector, requests_mock):
    with connector.context as cache:
        cache[KNOWN_DEVICES_KEY] = {"known": "fingerprint"}
    requests_mock.get(API_URL, status_code=401, json={"error": "Invalid Login/Password"})

    assert list(connector.get_assets()) == []
    connector.log_exception.assert_called_once()
    with connector.context as cache:
        assert cache[KNOWN_DEVICES_KEY] == {"known": "fingerprint"}


def test_stop_during_listing_merges_the_cache(connector, requests_mock):
    with connector.context as cache:
        cache[KNOWN_DEVICES_KEY] = {"known": "fingerprint"}
    requests_mock.get(API_URL, [page([SERVER], next_offset=100), page([LAPTOP])])

    assets = connector.get_assets()
    next(assets)
    connector.stop()
    assert list(assets) == []
    connector.update_checkpoint()

    with connector.context as cache:
        assert set(cache[KNOWN_DEVICES_KEY]) == {"known", "9479"}


def test_reset_checkpoint(connector):
    with connector.context as cache:
        cache[KNOWN_DEVICES_KEY] = {"known": "fingerprint"}

    connector.reset_checkpoint()

    with connector.context as cache:
        assert KNOWN_DEVICES_KEY not in cache


def test_fetch_cycle_pushes_changes_once(connector, requests_mock):
    requests_mock.get(API_URL, **page([SERVER, LAPTOP]))
    connector._http_session = Mock()
    connector._http_session.post.return_value = Mock(status_code=200, json=Mock(return_value={}))

    with patch("sekoia_automation.asset_connector.connector.time.sleep"):
        connector.asset_fetch_cycle()
        connector.asset_fetch_cycle()

    assert connector._http_session.post.call_count == 2


def test_devices_of_a_failed_push_are_retried_next_cycle(connector, requests_mock):
    requests_mock.get(API_URL, **page([SERVER, LAPTOP]))
    failed = Mock(status_code=500, json=Mock(return_value={"message": "error", "code": "error"}))
    succeeded = Mock(status_code=200, json=Mock(return_value={}))
    connector._http_session = Mock()
    connector._http_session.post.side_effect = [failed, succeeded, succeeded]

    with patch("sekoia_automation.asset_connector.connector.time.sleep"):
        connector.asset_fetch_cycle()
        connector.asset_fetch_cycle()

    pushed = [call.kwargs["json"]["items"][0]["device"]["uid"] for call in connector._http_session.post.call_args_list]
    assert pushed == ["9479", "10370", "9479"]
    with connector.context as cache:
        assert set(cache[KNOWN_DEVICES_KEY]) == {"9479", "10370"}


def test_get_mapped_fields_covers_the_requested_fields(connector):
    sources = {key.split(".")[0] for key in connector.get_mapped_fields()}
    assert sources <= set(ASSET_FIELDS)
