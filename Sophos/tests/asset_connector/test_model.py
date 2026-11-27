from sophos_module.asset_connector.model import SophosEndpoint, SophosEndpointsResponse, SophosUsersResponse


def test_endpoints_response():
    response = SophosEndpointsResponse.model_validate(
        {
            "items": [
                {
                    "id": "endpoint-1",
                    "type": "computer",
                    "hostname": "WIN-01",
                    "os": {"isServer": False, "platform": "windows", "majorVersion": 10},
                    "ipv4Addresses": ["192.0.2.10"],
                    "modules": [{"name": "endpointProtection", "version": "2024.1"}],
                    "group": {"id": "group-1", "name": "Workstations"},
                    "unknownField": "ignored",
                }
            ],
            "pages": {"size": 1, "maxSize": 500, "nextKey": "next"},
        }
    )

    endpoint = response.items[0]
    assert endpoint.hostname == "WIN-01"
    assert endpoint.os is not None and endpoint.os.platform == "windows"
    assert endpoint.modules[0].name == "endpointProtection"
    assert response.pages is not None and response.pages.nextKey == "next"


def test_endpoint_defaults():
    endpoint = SophosEndpoint()
    assert endpoint.id is None
    assert endpoint.ipv4Addresses == [] and endpoint.macAddresses == [] and endpoint.assignedProducts == []

    # the list defaults are not shared between instances
    endpoint.tags.append("tag")
    assert SophosEndpoint().tags == []


def test_users_response():
    response = SophosUsersResponse.model_validate(
        {
            "items": [
                {
                    "id": "user-1",
                    "name": "John Doe",
                    "exchangeLogin": "jdoe",
                    "groups": {"total": 1, "itemsCount": 1, "items": [{"id": "g", "displayName": "Admins"}]},
                    "source": {"type": "activeDirectory"},
                }
            ],
            "pages": {"current": 1, "size": 50, "maxSize": 100},
        }
    )

    user = response.items[0]
    assert user.exchangeLogin == "jdoe"
    assert user.groups is not None and user.groups.items[0].displayName == "Admins"
    assert user.source is not None and user.source.type == "activeDirectory"
    assert SophosUsersResponse().items == []
