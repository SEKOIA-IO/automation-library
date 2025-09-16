import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
import datetime

import requests_mock
from sekoia_automation.module import Module
from azure_ad.asset_connector.user_assets import EntraIDAssetConnector


@pytest.fixture
def test_entra_id_asset_connector(symphony_storage):
    module = Module()
    module_configuration: dict = {
        "tenant_id": "fake_tenant_id",
        "client_id": "fake_client_id",
        "client_secret": "fake_client_secret",
    }
    module.configuration = module_configuration

    test_entra_id_asset_connector = EntraIDAssetConnector(module=module, data_path=symphony_storage)
    test_entra_id_asset_connector.configuration = {
        "sekoia_base_url": "https://sekoia.io",
        "sekoia_api_key": "fake_api_key",
        "frequency": 60,
    }

    test_entra_id_asset_connector.log = Mock()
    test_entra_id_asset_connector.log_exception = Mock()

    yield test_entra_id_asset_connector


def mock_graph_service_client():
    """
    Returns a mock GraphServiceClient with users.get() async method returning a mock response.
    """
    mock_client = MagicMock()
    return mock_client


def mock_graph_service_client_for_users(mock_client, mock_user_list):
    """
    Returns a mock GraphServiceClient with users.get() async method returning a mock response with .value = mock_user_list and .odata_next_link = None.
    """
    mock_users = MagicMock()
    mock_users.get = AsyncMock(return_value=MagicMock(value=mock_user_list, odata_next_link=None))
    mock_client.users = mock_users
    return mock_client


def mock_graph_service_client_by_user_id(mock_client, mock_user):
    """
    Returns a mock GraphServiceClient with users.by_user_id() async method returning a mock response with .value = mock_user and .odata_next_link = None.
    """
    mock_by_user_id = MagicMock()
    mock_by_user_id.get = AsyncMock(return_value=mock_user)
    mock_users = MagicMock()
    mock_users.by_user_id.return_value = mock_by_user_id
    mock_client.users = mock_users
    return mock_client


def mock_graph_service_client_for_groups(mock_client, mock_group_list):
    """
    Returns a mock GraphServiceClient with users.by_user_id().member_of.get() async method
    returning a mock response with .value = mock_group_list and .odata_next_link = None.
    """
    mock_member_of = MagicMock()
    mock_member_of.get = AsyncMock(return_value=MagicMock(value=mock_group_list, odata_next_link=None))
    mock_by_user_id = MagicMock()
    mock_by_user_id.member_of = mock_member_of
    mock_users = MagicMock()
    mock_users.by_user_id.return_value = mock_by_user_id
    mock_client.users = mock_users
    return mock_client


def test_configuration(test_entra_id_asset_connector):
    assert test_entra_id_asset_connector.module.configuration["tenant_id"] == "fake_tenant_id"
    assert test_entra_id_asset_connector.module.configuration["client_id"] == "fake_client_id"
    assert test_entra_id_asset_connector.module.configuration["client_secret"] == "fake_client_secret"


def test_map_fields(test_entra_id_asset_connector):
    # Mocking the UserOCSFModel and UserOCSF for testing
    from sekoia_automation.asset_connector.models.ocsf.user import Group as UserOCSFGroup
    from msgraph.generated.models.user import User

    # Mocking the user and groups
    asset_user = User(
        user_principal_name="testuser@example.com",
        id="user_id",
        display_name="Test User",
        mail="testuser@example.com",
        created_date_time=datetime.datetime(2025, 7, 18, 14, 26, 43, tzinfo=datetime.timezone.utc),
    )
    has_mfa = True
    asset_groups = []
    result = test_entra_id_asset_connector.map_fields(asset_user, has_mfa, asset_groups)
    assert result.user.name == "testuser@example.com"
    assert result.user.uid == "user_id"
    assert result.user.has_mfa == has_mfa


@pytest.mark.asyncio
async def test_fetch_user_groups(test_entra_id_asset_connector):
    # Arrange
    user_id = "test-user-id"
    mock_group = MagicMock()
    mock_group.display_name = "Test Group"
    mock_group.id = "group-id"
    from msgraph.generated.models.group import Group

    mock_group.__class__ = Group
    mock_client = mock_graph_service_client()
    # Patch the client to return the mock response
    test_entra_id_asset_connector._client = mock_graph_service_client_for_groups(mock_client, [mock_group])

    # Act
    groups = await test_entra_id_asset_connector.fetch_user_groups(user_id)

    # Assert
    assert len(groups) == 1
    assert groups[0].name == "Test Group"
    assert groups[0].uid == "group-id"


@pytest.mark.asyncio
async def test_fetch_user_mfa(test_entra_id_asset_connector):
    user_id = "test-user-id"
    test_entra_id_asset_connector.client = mock_graph_service_client()

    # Mock authentication methods
    from msgraph.generated.models.microsoft_authenticator_authentication_method import (
        MicrosoftAuthenticatorAuthenticationMethod,
    )
    from msgraph.generated.models.software_oath_authentication_method import SoftwareOathAuthenticationMethod
    from msgraph.generated.models.phone_authentication_method import PhoneAuthenticationMethod

    # Case 1: User has Microsoft Authenticator (should return True)
    mock_method = MicrosoftAuthenticatorAuthenticationMethod()
    mock_response = MagicMock()
    mock_response.value = [mock_method]
    test_entra_id_asset_connector.client.users.by_user_id.return_value.authentication.methods.get = AsyncMock(
        return_value=mock_response
    )
    has_mfa = await test_entra_id_asset_connector.fetch_user_mfa(user_id)
    assert has_mfa is True

    # Case 2: User has Software OATH (should return True)
    mock_method = SoftwareOathAuthenticationMethod()
    mock_response.value = [mock_method]
    test_entra_id_asset_connector.client.users.by_user_id.return_value.authentication.methods.get = AsyncMock(
        return_value=mock_response
    )
    has_mfa = await test_entra_id_asset_connector.fetch_user_mfa(user_id)
    assert has_mfa is True

    # Case 3: User has Phone Authentication (should return True)
    mock_method = PhoneAuthenticationMethod()
    mock_response.value = [mock_method]
    test_entra_id_asset_connector.client.users.by_user_id.return_value.authentication.methods.get = AsyncMock(
        return_value=mock_response
    )
    has_mfa = await test_entra_id_asset_connector.fetch_user_mfa(user_id)
    assert has_mfa is True

    # Case 4: User has no MFA methods (should return False)
    mock_response.value = []
    test_entra_id_asset_connector.client.users.by_user_id.return_value.authentication.methods.get = AsyncMock(
        return_value=mock_response
    )
    has_mfa = await test_entra_id_asset_connector.fetch_user_mfa(user_id)
    assert has_mfa is False


@pytest.mark.asyncio
async def test_fetch_new_users(test_entra_id_asset_connector):
    # Arrange
    from msgraph.generated.models.user import User

    # Create mock users returned by Graph API
    mock_user1 = User(
        id="user1",
        user_principal_name="user1@example.com",
        display_name="User One",
        mail="user1@example.com",
        created_date_time=datetime.datetime(2025, 7, 18, 14, 26, 43, tzinfo=datetime.timezone.utc),
    )
    mock_user2 = User(
        id="user2",
        user_principal_name="user2@example.com",
        display_name="User Two",
        mail="user2@example.com",
        created_date_time=datetime.datetime(2025, 7, 18, 14, 26, 43, tzinfo=datetime.timezone.utc),
    )
    mock_users_response = MagicMock()
    mock_users_response.value = [mock_user1, mock_user2]
    mock_users_response.odata_next_link = None
    test_entra_id_asset_connector.client = mock_graph_service_client()

    # Patch the GraphServiceClient to return the mock users
    test_entra_id_asset_connector.client.users.get = AsyncMock(return_value=mock_users_response)

    # Patch fetch_user to avoid calling real sub-methods
    mock_user_ocsf_model = MagicMock()
    mock_user_ocsf_model.time = datetime.datetime.now().timestamp()
    test_entra_id_asset_connector.fetch_user = AsyncMock(return_value=mock_user_ocsf_model)

    # Act
    result = await test_entra_id_asset_connector.fetch_new_users()

    # Assert
    assert len(result) == 2
    test_entra_id_asset_connector.client.users.get.assert_awaited_once()
    assert test_entra_id_asset_connector.fetch_user.await_count == 2
    assert all(user is mock_user_ocsf_model for user in result)


@pytest.mark.asyncio
async def test_fetch_new_users_with_pagination(test_entra_id_asset_connector):
    from msgraph.generated.models.user import User

    test_entra_id_asset_connector.client = mock_graph_service_client()

    # First page of users
    mock_user1 = User(
        id="user1", user_principal_name="user1@example.com", display_name="User One", mail="user1@example.com"
    )
    mock_users_response_1 = MagicMock()
    mock_users_response_1.value = [mock_user1]
    mock_users_response_1.odata_next_link = "next-page-link"

    # Second page of users
    mock_user2 = User(
        id="user2", user_principal_name="user2@example.com", display_name="User Two", mail="user2@example.com"
    )
    mock_users_response_2 = MagicMock()
    mock_users_response_2.value = [mock_user2]
    mock_users_response_2.odata_next_link = None

    # Patch the GraphServiceClient to return the mock users for each page
    test_entra_id_asset_connector.client = MagicMock()
    test_entra_id_asset_connector.client.users.get = AsyncMock(return_value=mock_users_response_1)
    test_entra_id_asset_connector.client.users.with_url.return_value.get = AsyncMock(
        return_value=mock_users_response_2
    )

    # Patch fetch_user to avoid calling real sub-methods
    mock_user_ocsf_model_1 = MagicMock()
    mock_user_ocsf_model_1.time = datetime.datetime.now().timestamp()
    mock_user_ocsf_model_2 = MagicMock()
    mock_user_ocsf_model_2.time = datetime.datetime.now().timestamp()
    # Side effect for fetch_user: first call returns model 1, second call returns model 2
    test_entra_id_asset_connector.fetch_user = AsyncMock(side_effect=[mock_user_ocsf_model_1, mock_user_ocsf_model_2])

    # Act
    result = await test_entra_id_asset_connector.fetch_new_users()

    # Assert
    assert len(result) == 2
    test_entra_id_asset_connector.client.users.get.assert_awaited_once()
    test_entra_id_asset_connector.client.users.with_url.return_value.get.assert_awaited_once()
    assert test_entra_id_asset_connector.fetch_user.await_count == 2
    assert result[0] is mock_user_ocsf_model_1
    assert result[1] is mock_user_ocsf_model_2


def test_update_checkpoint(test_entra_id_asset_connector):
    """Test that update_checkpoint correctly updates the most_recent_date_seen in context."""
    # Arrange
    test_timestamp = 1640995200.0  # 2022-01-01 00:00:00 UTC
    test_entra_id_asset_connector.next_most_recent_date_seen = test_timestamp

    # Act
    test_entra_id_asset_connector.update_checkpoint()

    # Assert
    most_recent_date = test_entra_id_asset_connector.most_recent_date_seen
    assert most_recent_date is not None
    assert most_recent_date == "2022-01-01T00:00:00+00:00"


def test_update_checkpoint_with_different_timestamp(test_entra_id_asset_connector):
    """Test that update_checkpoint works with different timestamps."""
    # Arrange
    test_timestamp = 1672531200.0  # 2023-01-01 00:00:00 UTC
    test_entra_id_asset_connector.next_most_recent_date_seen = test_timestamp

    # Act
    test_entra_id_asset_connector.update_checkpoint()

    # Assert
    most_recent_date = test_entra_id_asset_connector.most_recent_date_seen
    assert most_recent_date is not None
    assert most_recent_date == "2023-01-01T00:00:00+00:00"
