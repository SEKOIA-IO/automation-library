from datetime import datetime

import uuid
from sekoiaio.operation_center.get_asset import GetAsset

module_base_url = "https://app.sekoia.fake/"
base_url = module_base_url + "api/v2/asset-management/assets/"
apikey = "fake_api_key"


def test_get_asset_by_uuid(requests_mock):
    action = GetAsset()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    asset_uuid = uuid.uuid4()
    arguments = {"uuid": str(asset_uuid)}
    response = {
        "uuid": "00000000-0000-0000-0000-000000000123",
        "entity_uuid": "00000000-0000-0000-0000-000000000000",
        "community_uuid": "00000000-0000-0000-0000-000000000000",
        "name": "test get asset",
        "type": "network",
        "criticality": 10,
        "created_at": "2024-10-09T17:30:11Z",
        "created_by": "abcdefab-5be7-4143-b936-7dc9eab3aeaf",
        "created_by_type": "avatar",
        "updated_at": "2024-10-11T17:30:11Z",
        "nb_atoms": 1,
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
        "source": "manual",
        "description": "test get asset action",
        "pending_recommendations": [],
    }
    requests_mock.get(base_url + str(asset_uuid), json=response)

    expected_result = {
        "uuid": "00000000-0000-0000-0000-000000000123",
        "name": "test get asset",
        "category": {"uuid": "1c646cb3-54c3-44cb-88d3-2db24de2fcf4", "name": "technical"},
        "description": "test get asset action",
        "criticity": {"value": 10, "display": "low"},
        "asset_type": {"uuid": "4aac4b72-14cf-4159-a4e5-32fa8c1f3da6", "name": "network"},
        "community_uuid": "00000000-0000-0000-0000-000000000000",
        "owners": [],
        "keys": [{"uuid": "e2440ef6-02af-4da0-ac7a-511821033d74", "name": "cidr-v4", "value": "10.100.100.0/24"}],
        "attributes": [{"uuid": "7a39c0cf-e470-4a06-afba-da2009fdc7d1", "name": "as", "value": "13336"}],
        "created_at": datetime.fromisoformat("2024-10-09T17:30:11Z"),
        "updated_at": datetime.fromisoformat("2024-10-11T17:30:11Z"),
    }
    results: dict = action.run(arguments)
    assert results == expected_result
    # add test for high criticity
    response["criticality"] = 70
    results: dict = action.run(arguments)
    assert results["criticity"]["display"] == "high"
    assert results["criticity"]["value"] == 70
    # add test for medium criticity
    response["criticality"] = 50
    results = action.run(arguments)
    assert results["criticity"]["display"] == "medium"
    assert results["criticity"]["value"] == 50


def test_get_asset_by_uuid_returns_none_if_http_error(requests_mock):
    action = GetAsset()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    asset_uuid = uuid.uuid4()
    arguments = {"uuid": str(asset_uuid)}

    requests_mock.get(base_url + str(asset_uuid), status_code=404)

    results: dict = action.run(arguments)
    assert results == None


def test_get_asset_transforms_criticity_levels(requests_mock):
    action = GetAsset()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    asset_uuid = uuid.uuid4()
    arguments = {"uuid": str(asset_uuid)}
    response = {
        "uuid": "00000000-0000-0000-0000-000000000123",
        "entity_uuid": "00000000-0000-0000-0000-000000000000",
        "community_uuid": "00000000-0000-0000-0000-000000000000",
        "name": "test get asset",
        "type": "network",
        "criticality": 10,
        "created_at": "2024-10-09T17:30:11Z",
        "created_by": "abcdefab-5be7-4143-b936-7dc9eab3aeaf",
        "created_by_type": "avatar",
        "updated_at": "2024-10-11T17:30:11Z",
        "nb_atoms": 1,
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
        "source": "manual",
        "description": "test get asset action",
        "pending_recommendations": [],
    }
    requests_mock.get(base_url + str(asset_uuid), json=response)

    expected_result = {
        "uuid": "00000000-0000-0000-0000-000000000123",
        "name": "test get asset",
        "category": {"uuid": "1c646cb3-54c3-44cb-88d3-2db24de2fcf4", "name": "technical"},
        "description": "test get asset action",
        "criticity": {"value": 10, "display": "low"},
        "asset_type": {"uuid": "4aac4b72-14cf-4159-a4e5-32fa8c1f3da6", "name": "network"},
        "community_uuid": "00000000-0000-0000-0000-000000000000",
        "owners": [],
        "keys": [{"uuid": "e2440ef6-02af-4da0-ac7a-511821033d74", "name": "cidr-v4", "value": "10.100.100.0/24"}],
        "attributes": [{"uuid": "7a39c0cf-e470-4a06-afba-da2009fdc7d1", "name": "as", "value": "13336"}],
        "created_at": datetime.fromisoformat("2024-10-09T17:30:11Z"),
        "updated_at": datetime.fromisoformat("2024-10-11T17:30:11Z"),
    }
    results: dict = action.run(arguments)
    assert results == expected_result
    response["criticality"] = 70
    results: dict = action.run(arguments)
    assert results["criticity"]["display"] == "high"
    assert results["criticity"]["value"] == 70
