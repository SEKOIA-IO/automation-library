import json
from unittest.mock import Mock

import pytest
import requests
import requests_mock as requests_mock_module
from sekoia_automation.asset_connector.models.ocsf.user import AccountTypeId, UserOCSFModel

from eset_modules import EsetModule
from eset_modules.asset_connector.models import EsetUser, EsetUserIdentity
from eset_modules.asset_connector.user_assets import EsetUserAssetConnector


@pytest.fixture
def data_storage(tmp_path):
    return tmp_path


@pytest.fixture
def test_connector(data_storage):
    module = EsetModule()
    module.configuration = {
        "region": "eu",
        "username": "testuser",
        "password": "testpassword",
    }

    connector = EsetUserAssetConnector(module=module, data_path=data_storage)
    connector.configuration = {
        "sekoia_base_url": "https://sekoia.io",
        "sekoia_api_key": "fake_api_key",
        "frequency": 60,
    }

    connector.log = Mock()
    connector.log_exception = Mock()

    connector.__dict__["client"] = requests.Session()

    yield connector


@pytest.fixture
def sample_user() -> EsetUser:
    return EsetUser(
        uuid="user-1",
        displayName="Jane Doe",
        primaryEmailAddress="jane@example.com",
        userGroupUuids=["group-a", "group-b"],
        department="Finance",
        jobTitle="Analyst",
        officeLocation="HQ",
        identities=[EsetUserIdentity(type="MICROSOFT", reference="jane@example.com")],
    )


@pytest.fixture
def sample_users_response():
    return {
        "users": [
            {
                "uuid": "user-1",
                "displayName": "Jane Doe",
                "primaryEmailAddress": "jane@example.com",
                "userGroupUuids": ["group-a"],
                "identities": [{"type": "MICROSOFT", "reference": "jane@example.com"}],
            }
        ],
        "nextPageToken": None,
        "totalSize": 1,
    }


# --- account type inference ---


@pytest.mark.parametrize(
    "provider,expected_id",
    [
        ("MICROSOFT", AccountTypeId.M365_TENANT),
        ("m365", AccountTypeId.M365_TENANT),
        ("Office365", AccountTypeId.M365_TENANT),
        ("GOOGLE", AccountTypeId.GOOGLE_WORKSPACE),
        ("google_workspace", AccountTypeId.GOOGLE_WORKSPACE),
        ("AZURE_AD", AccountTypeId.AZURE_AD_ACCOUNT),
        ("something", AccountTypeId.OTHER),
    ],
)
def test_resolve_account_type(test_connector, provider, expected_id):
    user = EsetUser(uuid="u", identities=[EsetUserIdentity(type=provider)])
    _, type_id = test_connector._resolve_account_type(user)
    assert type_id == expected_id


def test_resolve_account_type_no_identities(test_connector):
    _, type_id = test_connector._resolve_account_type(EsetUser(uuid="u"))
    assert type_id == AccountTypeId.OTHER


# --- map_fields ---


def test_map_fields_classification(test_connector, sample_user):
    result = test_connector.map_fields(sample_user)
    assert isinstance(result, UserOCSFModel)
    assert result.class_uid == 5003
    assert result.category_uid == 5
    assert result.type_uid == 500302
    assert result.activity_id == 2


def test_map_fields_user_and_account(test_connector, sample_user):
    result = test_connector.map_fields(sample_user)
    assert result.user.uid == "user-1"
    assert result.user.name == "Jane Doe"
    assert result.user.email_addr == "jane@example.com"
    assert result.user.account.type_id == AccountTypeId.M365_TENANT
    assert result.user.groups is not None
    assert {g.uid for g in result.user.groups} == {"group-a", "group-b"}


def test_map_fields_enrichments(test_connector, sample_user):
    result = test_connector.map_fields(sample_user)
    assert result.enrichments is not None
    names = {e.name: e.value for e in result.enrichments}
    assert names["department"] == "Finance"
    assert names["job_title"] == "Analyst"
    assert names["office_location"] == "HQ"


def test_map_fields_name_fallback_to_email(test_connector):
    user = EsetUser(uuid="u", primaryEmailAddress="x@y.com")
    result = test_connector.map_fields(user)
    assert result.user.name == "x@y.com"


def test_map_fields_name_fallback_to_uuid(test_connector):
    result = test_connector.map_fields(EsetUser(uuid="only-uuid"))
    assert result.user.name == "only-uuid"


def test_map_fields_no_enrichments(test_connector):
    result = test_connector.map_fields(EsetUser(uuid="u"))
    assert result.enrichments is None


def test_map_fields_json_serializable(test_connector, sample_user):
    result = test_connector.map_fields(sample_user)
    assert json.dumps(result.model_dump())


# --- fetch / ECOS gating ---


def test_fetch_users_single_page(test_connector, sample_users_response):
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/users", json=sample_users_response)
        pages = list(test_connector._fetch_users())

    assert len(pages) == 1
    assert pages[0][0].uuid == "user-1"


def test_fetch_users_pagination(test_connector):
    page1 = {"users": [{"uuid": "u1"}], "nextPageToken": "tok"}
    page2 = {"users": [{"uuid": "u2"}], "nextPageToken": None}
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/users", [{"json": page1}, {"json": page2}])
        pages = list(test_connector._fetch_users())

    assert len(pages) == 2


@pytest.mark.parametrize("status", [403, 501])
def test_fetch_users_ecos_unavailable_yields_nothing(test_connector, status):
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/users", status_code=status)
        pages = list(test_connector._fetch_users())

    assert pages == []
    test_connector.log.assert_called()


def test_fetch_users_server_error_raises(test_connector):
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/users", status_code=500)
        with pytest.raises(Exception):
            list(test_connector._fetch_users())


# --- get_assets ---


def test_get_assets_yields_ocsf(test_connector, sample_users_response):
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/users", json=sample_users_response)
        assets = list(test_connector.get_assets())

    assert len(assets) == 1
    assert isinstance(assets[0], UserOCSFModel)
    assert assets[0].user.uid == "user-1"


@pytest.mark.parametrize("status", [403, 501])
def test_get_assets_ecos_unavailable_empty(test_connector, status):
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/users", status_code=status)
        assets = list(test_connector.get_assets())

    assert assets == []


def test_update_checkpoint_persists_last_run(test_connector, sample_users_response):
    with requests_mock_module.Mocker() as m:
        m.get(f"{test_connector.base_url}/v1/users", json=sample_users_response)
        list(test_connector.get_assets())
        test_connector.update_checkpoint()

    with test_connector.context as cache:
        assert cache.get("last_run") is not None
