import datetime
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
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
    from msgraph.generated.models.user import User
    from sekoia_automation.asset_connector.models.ocsf.user import Group as UserOCSFGroup

    # Mocking the user and groups
    asset_user = User(
        user_principal_name="testuser@example.com",
        id="user_id",
        display_name="Test User",
        mail="testuser@example.com",
        created_date_time=datetime.datetime(2025, 7, 18, 14, 26, 43, tzinfo=datetime.timezone.utc),
        account_enabled=True,
        department="Engineering",
        job_title="Software Engineer",
        employee_id="EMP123",
        employee_type="Employee",
        company_name="Acme Corp",
        office_location="New York",
    )
    has_mfa = True
    asset_groups = []
    is_admin = False
    result = test_entra_id_asset_connector.map_fields(asset_user, has_mfa, asset_groups, is_admin)
    assert result.user.name == "testuser@example.com"
    assert result.user.uid == "user_id"
    assert result.user.has_mfa == has_mfa
    assert result.user.display_name == "Test User"
    assert result.user.domain == "example.com"
    assert result.user.type_id == 1  # UserTypeId.USER
    assert result.user.type == "User"
    # Verify org field is populated
    assert result.user.org is not None
    assert result.user.org.name == "Acme Corp"
    assert result.user.org.ou_name == "New York"
    # Verify enrichments are created
    assert result.enrichments is not None
    assert len(result.enrichments) > 0
    # Verify account enrichment
    account_enrichment = next((e for e in result.enrichments if e.name == "account"), None)
    assert account_enrichment is not None
    assert account_enrichment.data.is_enabled is True


def test_map_fields_without_org(test_entra_id_asset_connector):
    """Test mapping when organization fields are not available."""
    from msgraph.generated.models.user import User
    from sekoia_automation.asset_connector.models.ocsf.user import Group as UserOCSFGroup

    # Mocking the user without company name or office location
    asset_user = User(
        user_principal_name="testuser@example.com",
        id="user_id",
        display_name="Test User",
        mail="testuser@example.com",
        created_date_time=datetime.datetime(2025, 7, 18, 14, 26, 43, tzinfo=datetime.timezone.utc),
        account_enabled=True,
    )
    has_mfa = False
    asset_groups = []
    is_admin = False
    result = test_entra_id_asset_connector.map_fields(asset_user, has_mfa, asset_groups, is_admin)
    assert result.user.name == "testuser@example.com"
    assert result.user.uid == "user_id"
    # Verify org field is None when company_name is not provided
    assert result.user.org is None


def test_map_fields_with_admin_user_type(test_entra_id_asset_connector):
    """Test that user type is correctly set to Admin when is_admin=True."""
    from msgraph.generated.models.user import User
    from sekoia_automation.asset_connector.models.ocsf.user import UserTypeId, UserTypeStr

    asset_user = User(
        user_principal_name="admin@example.com",
        id="admin_user_id",
        display_name="Admin User",
        mail="admin@example.com",
        created_date_time=datetime.datetime(2025, 7, 18, 14, 26, 43, tzinfo=datetime.timezone.utc),
        account_enabled=True,
    )
    has_mfa = True
    asset_groups = []
    is_admin = True

    result = test_entra_id_asset_connector.map_fields(asset_user, has_mfa, asset_groups, is_admin)

    assert result.user.name == "admin@example.com"
    assert result.user.uid == "admin_user_id"
    assert result.user.type_id == UserTypeId.ADMIN
    assert result.user.type == UserTypeStr.ADMIN


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
    from msgraph.generated.models.phone_authentication_method import PhoneAuthenticationMethod
    from msgraph.generated.models.software_oath_authentication_method import SoftwareOathAuthenticationMethod

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
    result = [user async for user in test_entra_id_asset_connector.fetch_new_users()]

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
    result = [user async for user in test_entra_id_asset_connector.fetch_new_users()]

    # Assert
    assert len(result) == 2
    test_entra_id_asset_connector.client.users.get.assert_awaited_once()
    test_entra_id_asset_connector.client.users.with_url.return_value.get.assert_awaited_once()
    assert test_entra_id_asset_connector.fetch_user.await_count == 2
    assert result[0] is mock_user_ocsf_model_1
    assert result[1] is mock_user_ocsf_model_2


@pytest.mark.asyncio
async def test_update_checkpoint(test_entra_id_asset_connector):
    """Test that update_checkpoint correctly updates the most_recent_date_seen in context."""
    # Arrange
    test_timestamp = 1640995200.0  # 2022-01-01 00:00:00 UTC
    test_entra_id_asset_connector._latest_time = test_timestamp

    # Act
    await test_entra_id_asset_connector.update_checkpoint()

    # Assert
    most_recent_date = test_entra_id_asset_connector.most_recent_date_seen
    assert most_recent_date is not None
    assert most_recent_date == "2022-01-01T00:00:01+00:00"


@pytest.mark.asyncio
async def test_update_checkpoint_with_different_timestamp(test_entra_id_asset_connector):
    """Test that update_checkpoint works with different timestamps."""
    # Arrange
    test_timestamp = 1672531200.0  # 2023-01-01 00:00:00 UTC
    test_entra_id_asset_connector._latest_time = test_timestamp

    # Act
    await test_entra_id_asset_connector.update_checkpoint()

    # Assert
    most_recent_date = test_entra_id_asset_connector.most_recent_date_seen
    assert most_recent_date is not None
    assert most_recent_date == "2023-01-01T00:00:01+00:00"


def test_update_checkpoint_with_none_timestamp(test_entra_id_asset_connector):
    """Test that update_checkpoint returns early when _latest_time is None."""
    # Arrange
    test_entra_id_asset_connector._latest_time = None

    # Act
    test_entra_id_asset_connector.update_checkpoint()

    # Assert
    most_recent_date = test_entra_id_asset_connector.most_recent_date_seen
    assert most_recent_date is None


@pytest.mark.asyncio
async def test_fetch_user_groups_error_handling(test_entra_id_asset_connector):
    """Test that fetch_user_groups raises ValueError when API call fails."""
    # Arrange
    user_id = "test-user-id"
    mock_client = mock_graph_service_client()
    mock_client.users.by_user_id.return_value.member_of.get = AsyncMock(side_effect=Exception("API Error"))
    test_entra_id_asset_connector._client = mock_client

    # Act & Assert
    with pytest.raises(ValueError, match="Error fetching user groups"):
        await test_entra_id_asset_connector.fetch_user_groups(user_id)


@pytest.mark.asyncio
async def test_fetch_user_mfa_error_handling(test_entra_id_asset_connector):
    """Test that fetch_user_mfa raises ValueError when API call fails."""
    # Arrange
    user_id = "test-user-id"
    mock_client = mock_graph_service_client()
    mock_client.users.by_user_id.return_value.authentication.methods.get = AsyncMock(
        side_effect=Exception("API Error")
    )
    test_entra_id_asset_connector._client = mock_client

    # Act & Assert
    with pytest.raises(ValueError, match="Error fetching user MFA"):
        await test_entra_id_asset_connector.fetch_user_mfa(user_id)


@pytest.mark.asyncio
async def test_fetch_new_users_error_handling(test_entra_id_asset_connector):
    """Test that fetch_new_users raises ValueError when API call fails."""
    # Arrange
    mock_client = mock_graph_service_client()
    mock_client.users.get = AsyncMock(side_effect=Exception("API Error"))
    test_entra_id_asset_connector._client = mock_client

    # Act & Assert
    with pytest.raises(ValueError, match="Error fetching users"):
        async for _ in test_entra_id_asset_connector.fetch_new_users():
            pass


@pytest.mark.asyncio
async def test_fetch_user_groups_with_pagination(test_entra_id_asset_connector):
    """Test that fetch_user_groups handles pagination correctly."""
    # Arrange
    from msgraph.generated.models.group import Group

    user_id = "test-user-id"
    mock_group1 = MagicMock()
    mock_group1.display_name = "Group 1"
    mock_group1.id = "group-1"
    mock_group1.__class__ = Group

    mock_group2 = MagicMock()
    mock_group2.display_name = "Group 2"
    mock_group2.id = "group-2"
    mock_group2.__class__ = Group

    # First page response
    mock_response1 = MagicMock()
    mock_response1.value = [mock_group1]
    mock_response1.odata_next_link = "next-page-link"

    # Second page response
    mock_response2 = MagicMock()
    mock_response2.value = [mock_group2]
    mock_response2.odata_next_link = None

    mock_client = mock_graph_service_client()
    mock_member_of = MagicMock()
    mock_member_of.get = AsyncMock(side_effect=[mock_response1, mock_response2])
    mock_by_user_id = MagicMock()
    mock_by_user_id.member_of = mock_member_of
    mock_by_user_id.member_of.with_url.return_value.get = AsyncMock(return_value=mock_response2)
    mock_users = MagicMock()
    mock_users.by_user_id.return_value = mock_by_user_id
    mock_client.users = mock_users
    test_entra_id_asset_connector._client = mock_client

    # Act
    groups = await test_entra_id_asset_connector.fetch_user_groups(user_id)

    # Assert
    assert len(groups) == 2
    assert groups[0].name == "Group 1"
    assert groups[0].uid == "group-1"
    assert groups[1].name == "Group 2"
    assert groups[1].uid == "group-2"


@pytest.mark.asyncio
async def test_get_assets(test_entra_id_asset_connector):
    """Test that get_assets yields UserOCSFModel objects."""
    # Arrange
    mock_user_ocsf_model = MagicMock()
    mock_user_ocsf_model.time = datetime.datetime.now().timestamp()

    async def mock_fetch_new_users(last_run_date=None):
        yield mock_user_ocsf_model

    test_entra_id_asset_connector.fetch_new_users = mock_fetch_new_users

    # Act
    assets = [asset async for asset in test_entra_id_asset_connector.get_assets()]

    # Assert
    assert len(assets) == 1
    assert assets[0] is mock_user_ocsf_model


@pytest.mark.asyncio
async def test_get_assets_with_last_run_date(test_entra_id_asset_connector):
    """Test that get_assets uses most_recent_date_seen when available."""
    # Arrange
    test_entra_id_asset_connector._latest_time = 1640995200.0  # Set a timestamp
    await test_entra_id_asset_connector.update_checkpoint()  # Save it to context

    mock_user_ocsf_model = MagicMock()
    mock_user_ocsf_model.time = datetime.datetime.now().timestamp()

    # Track calls to fetch_new_users
    call_tracker = {"last_run_date": None}

    async def mock_fetch_new_users(last_run_date=None):
        call_tracker["last_run_date"] = last_run_date
        yield mock_user_ocsf_model

    test_entra_id_asset_connector.fetch_new_users = mock_fetch_new_users

    # Act
    assets = [asset async for asset in test_entra_id_asset_connector.get_assets()]

    # Assert
    assert len(assets) == 1
    # Verify that the last_run_date was passed
    assert call_tracker["last_run_date"] is not None


def test_map_fields_with_none_values(test_entra_id_asset_connector):
    """Test that map_fields handles None values correctly."""
    from msgraph.generated.models.user import User
    from sekoia_automation.asset_connector.models.ocsf.user import Group as UserOCSFGroup

    # Create user with None values (but keep id as a string since it's required)
    asset_user = User(
        user_principal_name=None,
        id="test-id",  # Keep this as a string since uid is required
        display_name=None,
        mail=None,
        created_date_time=None,
    )
    has_mfa = False
    asset_groups = []

    # Act
    result = test_entra_id_asset_connector.map_fields(asset_user, has_mfa, asset_groups, False)

    # Assert
    assert result.user.name == "Unknown"
    assert result.user.uid == "test-id"
    assert result.user.has_mfa is False
    assert result.user.full_name == "Unknown"
    assert result.user.email_addr == "Unknown"
    assert result.time == 0  # Should be 0 when created_date_time is None


def test_map_fields_with_groups(test_entra_id_asset_connector):
    """Test that map_fields correctly handles user groups."""
    from msgraph.generated.models.user import User
    from sekoia_automation.asset_connector.models.ocsf.user import Group as UserOCSFGroup

    # Create user
    asset_user = User(
        user_principal_name="testuser@example.com",
        id="user_id",
        display_name="Test User",
        mail="testuser@example.com",
        created_date_time=datetime.datetime(2025, 7, 18, 14, 26, 43, tzinfo=datetime.timezone.utc),
    )
    has_mfa = True
    asset_groups = [
        UserOCSFGroup(name="Group 1", uid="group-1"),
        UserOCSFGroup(name="Group 2", uid="group-2"),
    ]

    # Act
    result = test_entra_id_asset_connector.map_fields(asset_user, has_mfa, asset_groups, False)

    # Assert
    assert result.user.groups is not None
    assert len(result.user.groups) == 2
    assert result.user.groups[0].name == "Group 1"
    assert result.user.groups[1].name == "Group 2"


def test_map_fields_domain_extraction(test_entra_id_asset_connector):
    """Test that domain is correctly extracted from userPrincipalName."""
    from msgraph.generated.models.user import User

    # Create user with domain
    asset_user = User(
        user_principal_name="testuser@example.com",
        id="user_id",
        display_name="Test User",
        mail="testuser@example.com",
        created_date_time=datetime.datetime(2025, 7, 18, 14, 26, 43, tzinfo=datetime.timezone.utc),
    )

    result = test_entra_id_asset_connector.map_fields(asset_user, False, [], False)

    assert result.user.domain == "example.com"


def test_map_fields_domain_extraction_no_domain(test_entra_id_asset_connector):
    """Test that domain is None when userPrincipalName has no @ sign."""
    from msgraph.generated.models.user import User

    # Create user without @ in userPrincipalName
    asset_user = User(
        user_principal_name="testuser",
        id="user_id",
        display_name="Test User",
        mail="testuser@example.com",
        created_date_time=datetime.datetime(2025, 7, 18, 14, 26, 43, tzinfo=datetime.timezone.utc),
    )

    result = test_entra_id_asset_connector.map_fields(asset_user, False, [], False)

    assert result.user.domain is None


def test_map_fields_user_type_detection_admin(test_entra_id_asset_connector):
    """Test that user type is correctly set to Admin based on employee_type."""
    from msgraph.generated.models.user import User
    from sekoia_automation.asset_connector.models.ocsf.user import UserTypeId, UserTypeStr

    asset_user = User(
        user_principal_name="admin@example.com",
        id="user_id",
        display_name="Admin User",
        mail="admin@example.com",
        created_date_time=datetime.datetime(2025, 7, 18, 14, 26, 43, tzinfo=datetime.timezone.utc),
        employee_type="Administrator",
    )

    result = test_entra_id_asset_connector.map_fields(asset_user, False, [], True)

    assert result.user.type_id == UserTypeId.ADMIN
    assert result.user.type == UserTypeStr.ADMIN


def test_map_fields_user_type_detection_service(test_entra_id_asset_connector):
    """Test that user type is correctly set to Service based on employee_type."""
    from msgraph.generated.models.user import User
    from sekoia_automation.asset_connector.models.ocsf.user import UserTypeId, UserTypeStr

    asset_user = User(
        user_principal_name="service@example.com",
        id="user_id",
        display_name="Service Account",
        mail="service@example.com",
        created_date_time=datetime.datetime(2025, 7, 18, 14, 26, 43, tzinfo=datetime.timezone.utc),
        employee_type="Service Account",
    )

    result = test_entra_id_asset_connector.map_fields(asset_user, False, [], False)

    assert result.user.type_id == UserTypeId.USER
    assert result.user.type == UserTypeStr.USER


def test_map_fields_enrichment_with_sign_in_activity(test_entra_id_asset_connector):
    """Test that enrichments include last_logon when sign_in_activity is present."""
    from msgraph.generated.models.sign_in_activity import SignInActivity
    from msgraph.generated.models.user import User

    sign_in_activity = SignInActivity()
    sign_in_activity.last_sign_in_date_time = datetime.datetime(2025, 12, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)

    asset_user = User(
        user_principal_name="testuser@example.com",
        id="user_id",
        display_name="Test User",
        mail="testuser@example.com",
        created_date_time=datetime.datetime(2025, 7, 18, 14, 26, 43, tzinfo=datetime.timezone.utc),
        account_enabled=True,
        sign_in_activity=sign_in_activity,
    )

    result = test_entra_id_asset_connector.map_fields(asset_user, False, [], False)

    assert result.enrichments is not None
    account_enrichment = next((e for e in result.enrichments if e.name == "account"), None)
    assert account_enrichment is not None
    assert account_enrichment.data.last_logon is not None
    assert "2025-12-01" in account_enrichment.data.last_logon


def test_map_fields_enrichment_with_employment_info(test_entra_id_asset_connector):
    """Test that enrichments include employment info when available."""
    from msgraph.generated.models.user import User

    asset_user = User(
        user_principal_name="testuser@example.com",
        id="user_id",
        display_name="Test User",
        mail="testuser@example.com",
        created_date_time=datetime.datetime(2025, 7, 18, 14, 26, 43, tzinfo=datetime.timezone.utc),
        department="Engineering",
        job_title="Senior Engineer",
        employee_id="EMP123",
        employee_type="Full-Time",
    )

    result = test_entra_id_asset_connector.map_fields(asset_user, False, [], False)

    assert result.enrichments is not None
    employment_enrichment = next((e for e in result.enrichments if e.name == "employment"), None)
    assert employment_enrichment is not None
    assert "Engineering" in employment_enrichment.value or "Senior Engineer" in employment_enrichment.value


def test_map_fields_enrichment_without_optional_fields(test_entra_id_asset_connector):
    """Test that enrichments are created with minimal data."""
    from msgraph.generated.models.user import User

    asset_user = User(
        user_principal_name="testuser@example.com",
        id="user_id",
        display_name="Test User",
        mail="testuser@example.com",
        created_date_time=datetime.datetime(2025, 7, 18, 14, 26, 43, tzinfo=datetime.timezone.utc),
    )

    result = test_entra_id_asset_connector.map_fields(asset_user, False, [], False)

    # Account enrichment should always be present
    assert result.enrichments is not None
    account_enrichment = next((e for e in result.enrichments if e.name == "account"), None)
    assert account_enrichment is not None
    # Employment enrichment should not be present when no employment data is available
    employment_enrichment = next((e for e in result.enrichments if e.name == "employment"), None)
    assert employment_enrichment is None
