import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock

from ldap3.core.timezone import OffsetTzInfo
from sekoia_automation.asset_connector.models.ocsf.user import UserOCSFModel, UserTypeStr, UserTypeId, AccountTypeId

from microsoft_ad.asset_connectors.user_assets import MicrosoftADUserAssetConnector


@pytest.fixture
def mock_module():
    module = Mock()
    module.configuration.basedn = "DC=example,DC=com"
    return module


@pytest.fixture
def connector(tmp_path, mock_module):
    connector = object.__new__(MicrosoftADUserAssetConnector)
    connector.module = mock_module
    connector._data_path = tmp_path
    connector.log = Mock()
    connector.error = Mock()
    connector._latest_time = None
    connector.ldap_client = Mock()
    connector.context = MagicMock()
    return connector


def test_user_ldap_query_without_checkpoint(connector):
    connector.context.__enter__().get.return_value = None

    query = connector.user_ldap_query

    assert query == "(&(objectCategory=person)(objectClass=user))"


def test_user_ldap_query_with_checkpoint(connector):
    connector.context.__enter__().get.return_value = "20240101120000.0Z"

    query = connector.user_ldap_query

    assert query == "(&(objectCategory=person)(objectClass=user)(whenCreated>=20240101120000.0Z))"


def test_update_checkpoint_with_latest_time(connector):
    connector._latest_time = "20240101120000.0Z"

    connector.update_checkpoint()

    connector.context.__enter__().__setitem__.assert_called_once_with("most_recent_datetime", "20240101120000.0Z")


def test_update_checkpoint_without_latest_time(connector):
    connector._latest_time = None

    connector.update_checkpoint()

    connector.context.__enter__().__setitem__.assert_not_called()


def test_user_metadata_object(connector):
    metadata = connector.user_metadata_object()

    assert metadata.product.name == "Microsoft Active Directory"
    assert metadata.product.version == "N/A"
    assert metadata.version == "1.6.0"


def test_compute_enabling_condition_enabled(connector):
    user_attr = {"userAccountControl": 512}

    result = connector.compute_enabling_condition(user_attr)

    assert result is True


def test_compute_enabling_condition_disabled(connector):
    user_attr = {"userAccountControl": 514}

    result = connector.compute_enabling_condition(user_attr)

    assert result is False


def test_convert_last_logon_to_timestamp(connector):
    last_logon = datetime(2024, 1, 1, 12, 0, 0, tzinfo=OffsetTzInfo(offset=0, name="UTC"))

    timestamp = connector.convert_last_logon_to_timestamp(last_logon)

    expected_timestamp = str(int(datetime(2024, 1, 1, 12, 0, 0, tzinfo=OffsetTzInfo(offset=0, name="UTC")).timestamp()))
    assert timestamp == expected_timestamp


def test_enrich_metadata(connector):
    user_attr = {"userAccountControl": 512, "lastLogon": "2024-01-01", "badPwdCount": 0, "logonCount": 10}

    enrichments = connector.enrich_metadata(user_attr)

    assert len(enrichments) == 1
    assert enrichments[0].name == "login"
    assert enrichments[0].value == "infos"
    assert enrichments[0].data.is_enabled is True
    assert enrichments[0].data.number_of_logons == 10


def test_compute_user_type_admin(connector):
    user_attr = {"member_of": ["CN=Domain Admins,DC=example,DC=com"]}

    user_type, user_type_id = connector.compute_user_type(user_attr)

    assert user_type == UserTypeStr.ADMIN
    assert user_type_id == UserTypeId.ADMIN


def test_compute_user_type_regular_user(connector):
    user_attr = {"member_of": ["CN=Users,DC=example,DC=com"]}

    user_type, user_type_id = connector.compute_user_type(user_attr)

    assert user_type == UserTypeStr.USER
    assert user_type_id == UserTypeId.USER


def test_get_user_groups(connector):
    user_attr = {"member_of": ["CN=Group1,DC=example,DC=com", "CN=Group2,DC=example,DC=com"]}

    groups = connector.get_user_groups(user_attr)

    assert len(groups) == 2
    assert groups[0].name == "CN=Group1,DC=example,DC=com"
    assert groups[1].name == "CN=Group2,DC=example,DC=com"


def test_user_oscf_object(connector):
    user_attr = {
        "firstName": "John",
        "lastName": "Doe",
        "userPrincipalName": "john.doe@example.com",
        "objectSid": "S-1-5-21-123456",
        "objectGUID": "guid-123",
        "displayName": "John Doe",
        "mail": "john.doe@example.com",
        "distinguishedName": "CN=John Doe,DC=example,DC=com",
        "member_of": ["CN=Users,DC=example,DC=com"],
    }

    user_ocsf = connector.user_oscf_object(user_attr)

    assert user_ocsf.name == "John Doe"
    assert user_ocsf.uid == "S-1-5-21-123456"
    assert user_ocsf.account.name == "john.doe@example.com"
    assert user_ocsf.account.type_id == AccountTypeId.LDAP_ACCOUNT
    assert user_ocsf.email_addr == "john.doe@example.com"


def test_map_user_fields(connector):
    user = {
        "attributes": {
            "firstName": "Jane",
            "lastName": "Smith",
            "userPrincipalName": "jane.smith@example.com",
            "objectSid": "S-1-5-21-654321",
            "objectGUID": "guid-456",
            "displayName": "Jane Smith",
            "mail": "jane.smith@example.com",
            "distinguishedName": "CN=Jane Smith,DC=example,DC=com",
            "member_of": [],
            "whenCreated": datetime(2024, 1, 1, 12, 0, 0),
            "userAccountControl": 512,
            "lastLogon": "2024-01-01",
            "badPwdCount": 0,
            "logonCount": 5,
        }
    }

    user_model = connector.map_user_fields(user)

    assert isinstance(user_model, UserOCSFModel)
    assert user_model.activity_id == 2
    assert user_model.activity_name == "Collect"
    assert user_model.user.name == "Jane Smith"
    assert user_model.time == int(datetime(2024, 1, 1, 12, 0, 0).timestamp())


def test_get_users_generator(connector):
    mock_entry = {
        "dn": "CN=Test User,DC=example,DC=com",
        "attributes": {"userPrincipalName": "test@example.com", "whenCreated": datetime(2024, 1, 1, 12, 0, 0)},
    }

    connector.ldap_client.extend.standard.paged_search.return_value = iter([mock_entry])

    users = list(connector.get_users_generator())

    assert len(users) == 1
    assert users[0]["dn"] == "CN=Test User,DC=example,DC=com"
    assert connector._latest_time == "20240101120000.0Z"


def test_get_assets(connector):
    mock_user = {
        "dn": "CN=Asset User,DC=example,DC=com",
        "attributes": {
            "firstName": "Asset",
            "lastName": "User",
            "userPrincipalName": "asset@example.com",
            "objectSid": "S-1-5-21-111",
            "whenCreated": datetime(2024, 1, 1, 12, 0, 0),
            "userAccountControl": 512,
        },
    }

    connector.get_users_generator = Mock(return_value=iter([mock_user]))

    assets = list(connector.get_assets())

    assert len(assets) == 1
    assert isinstance(assets[0], UserOCSFModel)


def test_get_assets_handles_exception(connector):
    mock_user = {"dn": "CN=Invalid User,DC=example,DC=com", "attributes": {}}

    connector.get_users_generator = Mock(return_value=iter([mock_user]))

    assets = list(connector.get_assets())

    assert len(assets) == 0
