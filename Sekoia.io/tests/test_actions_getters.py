import pytest

from sekoiaio.operation_center import GetEntity, GetIntake
from sekoiaio.workspace import GetCommunity

module_base_url = "http://fake.url/"
base_url = module_base_url + "api/v1/sic/"
apikey = "fake_api_key"


@pytest.fixture
def module_config():
    return {
        "base_url": "http://fake.url/",
        "api_key": "fake_api_key",
    }


def test_get_community(module_config, requests_mock):
    action = GetCommunity()
    action.module.configuration = module_config

    community_uuid = "fake_uuid"
    expected_response = {
        "uuid": community_uuid,
        "name": "Detection",
        "description": "Community used for detection tests",
        "homepage_url": "",
        "picture_mode": "custom",
        "created_at": "2021-06-23 09:13:22.077939",
        "updated_at": "2021-06-23 09:15:09.778049",
        "created_by": "4abd1b95-ccee-44ba-af50-5c3b18c40b9f",
        "created_by_type": "avatar",
        "is_parent": False,
        "parent_community_uuid": None,
        "subcommunities": [],
        "is_mfa_enforced": None,
        "session_timeout": None,
        "disable_inactive_avatars": False,
        "disabled": False,
    }

    requests_mock.get(
        f"http://fake.url/api/v1/communities/{community_uuid}",
        json=expected_response,
    )

    results = action.run({"uuid": community_uuid})
    assert results == expected_response


def test_get_intake(module_config, requests_mock):
    action = GetIntake()
    action.module.configuration = module_config

    intake_uuid = "fake_uuid"
    expected_response = {
        "uuid": intake_uuid,
        "name": "Test AWS WAF",
        "community_uuid": "510f75ca-563d-4949-882e-e66bcfe8c524",
        "entity_uuid": "63af91e9-2e70-4151-a7af-e82f809753f6",
        "format_uuid": "46e45417-187b-45bb-bf81-30df7b1963a0",
        "intake_key": "MGV1DUTUjBFBwtqqmHDzSE9VWhddeiin",
        "created_at": "2024-06-06T10:06:19.561995Z",
        "created_by": "4f66b6da-924a-47ee-8638-972935a07f02",
        "created_by_type": "avatar",
        "updated_at": "2024-06-06T10:06:19.953978Z",
        "updated_by": None,
        "updated_by_type": None,
        "entity": {"name": "Dunder Mifflin", "uuid": "7e7f075d-a6a2-45b4-bfac-592ee0957d2e"},
        "is_custom_format": False,
        "connector_configuration_uuid": "0468c38c-c0b8-4717-8919-c7dae7d35051",
        "status": "STOPPED",
    }

    requests_mock.get(
        f"http://fake.url/api/v1/sic/conf/intakes/{intake_uuid}",
        json=expected_response,
    )

    results = action.run({"uuid": intake_uuid})
    assert results == expected_response


def test_get_entity(module_config, requests_mock):
    action = GetEntity()
    action.module.configuration = module_config

    entity_uuid = "fake_uuid"
    expected_response = {
        "uuid": entity_uuid,
        "name": "Dunder Mifflin",
        "entity_id": "dunder_mifflin",
        "alerts_generation": "e54510b7-13dc-4773-ad0d-f8b13b9a939d",
        "description": "Dunder Mifflin Paper Company, Inc.",
        "community_uuid": "510f75ca-563d-4949-882e-e66bcfe8c524",
        "number_of_intakes": 20,
    }

    requests_mock.get(
        f"http://fake.url/api/v1/sic/conf/entities/{entity_uuid}",
        json=expected_response,
    )

    results = action.run({"uuid": entity_uuid})
    assert results == expected_response
