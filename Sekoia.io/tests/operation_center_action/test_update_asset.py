import uuid

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
