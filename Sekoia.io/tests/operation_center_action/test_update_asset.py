import uuid

import pytest
from pydantic import ValidationError

from sekoiaio.operation_center.update_asset import UpdateAsset

module_base_url = "https://app.sekoia.fake/"
base_url = module_base_url + "api/v2/asset-management/assets/"
apikey = "fake_api_key"


def test_update_asset_by_uuid(requests_mock):
    action = UpdateAsset()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    asset_uuid = uuid.uuid4()
    arguments = {"uuid": str(asset_uuid)}
    response = {
        "uuid": "00000000-0000-0000-0000-000000000123",
        "entity_uuid": "00000000-0000-0000-0000-000000000000",
        "name": "test get asset",
        "type": "network",
        "criticality": 10,
        "atoms": {
            "cidrv6": [],
            "cidrv4": ["10.100.100.0/24"],
        },
        "props": {
            "asn": "13336",
        },
        "tags": [],
        "revoked": False,
        "reviewed": False,
        "description": "test get asset action",
        "pending_recommendations": [],
    }
    requests_mock.put(base_url + str(asset_uuid), json=response)

    results: dict = action.run(arguments)
    assert results == response


def test_update_asset_by_uuid_returns_none_if_http_error(requests_mock):
    action = UpdateAsset()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    asset_uuid = uuid.uuid4()
    arguments = {"uuid": str(asset_uuid)}

    requests_mock.put(base_url + str(asset_uuid), status_code=404)

    results: dict = action.run(arguments)
    assert results is None


def test_update_asset_by_uuid_returns_none_if_uuid_empty(requests_mock):
    action = UpdateAsset()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    arguments = {"uuid": ""}

    with pytest.raises(ValidationError):
        action.run(arguments)
    assert requests_mock.call_count == 0


def test_update_asset_by_uuid_returns_none_if_uuid_invalid(requests_mock):
    action = UpdateAsset()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    arguments = {"uuid": "not-a-uuid"}

    with pytest.raises(ValidationError):
        action.run(arguments)
    assert requests_mock.call_count == 0


def test_update_asset_with_tags_as_list(requests_mock):
    action = UpdateAsset()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    asset_uuid = uuid.uuid4()
    tags_list = ["tag1", "tag2", "tag3"]
    arguments = {"uuid": str(asset_uuid), "tags": list(tags_list)}
    response = {
        "uuid": "00000000-0000-0000-0000-000000000123",
        "entity_uuid": "00000000-0000-0000-0000-000000000000",
        "name": "test get asset",
        "type": "network",
        "criticality": 10,
        "atoms": {
            "cidrv6": [],
            "cidrv4": ["10.100.100.0/24"],
        },
        "props": {
            "asn": "13336",
        },
        "tags": tags_list,
        "revoked": False,
        "reviewed": False,
        "description": "test get asset action",
        "pending_recommendations": [],
    }
    requests_mock.put(base_url + str(asset_uuid), json=response)

    results: dict = action.run(arguments)
    assert results == response
    assert requests_mock.last_request.json()["tags"] == tags_list


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("entity_uuid", "not-a-uuid"),
        ("name", "a"),
        ("type", "not-a-valid-type"),
        ("criticality", -1),
        ("criticality", 101),
        ("atoms", {"cidrv4": {"nested": "not-a-scalar"}}),
    ],
)
def test_update_asset_rejects_invalid_optional_fields(requests_mock, field, value):
    action = UpdateAsset()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    asset_uuid = uuid.uuid4()
    arguments = {"uuid": str(asset_uuid), field: value}

    with pytest.raises(ValidationError):
        action.run(arguments)
    assert requests_mock.call_count == 0


def test_update_asset_accepts_valid_optional_fields(requests_mock):
    action = UpdateAsset()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    asset_uuid = uuid.uuid4()
    entity_uuid = uuid.uuid4()
    arguments = {
        "uuid": str(asset_uuid),
        "entity_uuid": str(entity_uuid),
        "name": "ok",
        "type": "host",
        "criticality": 50,
        "atoms": {"cidrv4": ["10.0.0.0/24"], "hostname": "example"},
    }
    response = {"uuid": str(asset_uuid)}
    requests_mock.put(base_url + str(asset_uuid), json=response)

    results: dict = action.run(arguments)
    assert results == response
    sent = requests_mock.last_request.json()
    assert sent["entity_uuid"] == str(entity_uuid)
    assert sent["name"] == "ok"
    assert sent["type"] == "host"
    assert sent["criticality"] == 50
    assert sent["atoms"] == {"cidrv4": ["10.0.0.0/24"], "hostname": "example"}
