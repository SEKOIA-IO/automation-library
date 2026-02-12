"""Unit tests for OktaUserAssetConnector."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sekoia_automation.asset_connector.models.ocsf.user import Group, UserOCSFModel

from okta_modules.asset_connector.user_assets import OktaUserAssetConnector


class TestOktaUserAssetConnector:
    """Test cases for OktaUserAssetConnector class."""

    @pytest.fixture
    def mock_connector(self):
        """Create a mock connector instance for testing."""
        with patch("okta_modules.asset_connector.user_assets.PersistentJSON") as mock_persistent_json:
            # Create a mock data path
            mock_data_path = MagicMock()
            mock_data_path.absolute.return_value = "/test/path"

            # Create the connector instance with mocked parent init
            with patch.object(OktaUserAssetConnector, "__init__", lambda self: None):
                connector = OktaUserAssetConnector()

                # Set up the required attributes
                connector._data_path = mock_data_path
                connector.module = MagicMock()
                connector.module.configuration = {"base_url": "https://test.okta.com", "apikey": "test_api_key"}
                connector.log = MagicMock()
                connector.context = mock_persistent_json.return_value

                return connector

    @pytest.fixture
    def mock_okta_client(self):
        """Create a mock Okta client."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def sample_groups_data(self):
        """Sample groups data for testing."""
        group1 = MagicMock()
        group1.id = "group1"
        group1.profile.name = "Test Group 1"
        group1.profile.description = "Test Description 1"

        group2 = MagicMock()
        group2.id = "group2"
        group2.profile.name = "Test Group 2"
        group2.profile.description = "Test Description 2"

        return [group1, group2]

    @pytest.fixture
    def sample_user_data(self):
        """Sample user data for testing."""
        user = MagicMock()
        user.id = "user123"
        user.created = "2023-01-01T00:00:00.000Z"
        user.profile.login = "test.user@example.com"
        user.profile.firstName = "Test"
        user.profile.lastName = "User"
        user.profile.email = "test.user@example.com"
        user.profile.displayName = "Test User"
        user.profile.userType = "User"
        return user

    @pytest.fixture
    def sample_users_data(self):
        """Sample users data for testing."""
        user1 = MagicMock()
        user1.id = "user1"
        user1.created = "2023-01-01T00:00:00.000Z"
        user1.profile.login = "user1@example.com"
        user1.profile.firstName = "User"
        user1.profile.lastName = "One"
        user1.profile.email = "user1@example.com"

        user2 = MagicMock()
        user2.id = "user2"
        user2.created = "2023-01-02T00:00:00.000Z"
        user2.profile.login = "user2@example.com"
        user2.profile.firstName = "User"
        user2.profile.lastName = "Two"
        user2.profile.email = "user2@example.com"

        return [user1, user2]

    @pytest.mark.asyncio
    async def test_get_user_groups_success(self, mock_connector, mock_okta_client, sample_groups_data):
        """Test successful retrieval of user groups."""
        # Setup
        mock_connector.client = mock_okta_client
        mock_response = MagicMock()
        mock_response.has_next.return_value = False
        mock_okta_client.list_user_groups.return_value = (sample_groups_data, mock_response, None)
        # Mock get_group_privileges to avoid calling list_group_assigned_roles
        mock_connector.get_group_privileges = AsyncMock(return_value=["privilege1"])

        # Execute
        result = await mock_connector.get_user_groups("user123")

        # Verify
        assert len(result) == 2
        assert isinstance(result[0], Group)
        assert result[0].name == "Test Group 1"
        assert result[0].uid == "group1"
        assert result[0].desc == "Test Description 1"
        assert result[0].privileges == ["privilege1"]
        assert result[1].name == "Test Group 2"
        assert result[1].uid == "group2"
        assert result[1].desc == "Test Description 2"
        assert result[1].privileges == ["privilege1"]
        mock_okta_client.list_user_groups.assert_called_once_with("user123")

    @pytest.mark.asyncio
    async def test_get_user_groups_with_pagination(self, mock_connector, mock_okta_client, sample_groups_data):
        """Test user groups retrieval with pagination."""
        # Setup
        mock_connector.client = mock_okta_client
        # Mock get_group_privileges to avoid calling list_group_assigned_roles
        mock_connector.get_group_privileges = AsyncMock(return_value=[])

        # First page
        group3 = MagicMock()
        group3.id = "group3"
        group3.profile.name = "Test Group 3"
        group3.profile.description = "Test Description 3"

        mock_response = MagicMock()
        mock_response.has_next.return_value = True
        mock_response.next = AsyncMock(return_value=([group3], mock_response, None))

        # Second page
        mock_response_2 = MagicMock()
        mock_response_2.has_next.return_value = False
        mock_response.next.return_value = ([group3], mock_response_2, None)

        mock_okta_client.list_user_groups.return_value = (sample_groups_data, mock_response, None)

        # Execute
        result = await mock_connector.get_user_groups("user123")

        # Verify
        assert len(result) == 3
        assert result[2].name == "Test Group 3"
        assert result[2].uid == "group3"
        mock_okta_client.list_user_groups.assert_called_once_with("user123")
        mock_response.next.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_groups_error(self, mock_connector, mock_okta_client):
        """Test user groups retrieval with error."""
        # Setup
        mock_connector.client = mock_okta_client
        mock_okta_client.list_user_groups.return_value = (None, None, "API Error")

        # Execute
        result = await mock_connector.get_user_groups("user123")

        # Verify
        assert result == []
        mock_connector.log.assert_called_with(
            "Error while fetching groups for user user123: API Error", level="warning"
        )

    @pytest.mark.asyncio
    async def test_get_user_groups_no_groups(self, mock_connector, mock_okta_client):
        """Test user groups retrieval when no groups found."""
        # Setup
        mock_connector.client = mock_okta_client
        mock_response = MagicMock()
        mock_response.has_next.return_value = False
        mock_okta_client.list_user_groups.return_value = ([], mock_response, None)

        # Execute
        result = await mock_connector.get_user_groups("user123")

        # Verify
        assert result == []
        mock_connector.log.assert_called_with("No groups found for user user123", level="warning")

    @pytest.mark.asyncio
    async def test_get_user_mfa_success(self, mock_connector, mock_okta_client):
        """Test successful MFA status retrieval."""
        # Setup
        mock_connector.client = mock_okta_client
        mock_factors = [MagicMock(), MagicMock()]
        mock_okta_client.list_factors.return_value = (mock_factors, None, None)

        # Execute
        result = await mock_connector.get_user_mfa("user123")

        # Verify
        assert result is True
        mock_okta_client.list_factors.assert_called_once_with("user123")

    @pytest.mark.asyncio
    async def test_get_user_mfa_no_factors(self, mock_connector, mock_okta_client):
        """Test MFA status when no factors found."""
        # Setup
        mock_connector.client = mock_okta_client
        mock_okta_client.list_factors.return_value = ([], None, None)

        # Execute
        result = await mock_connector.get_user_mfa("user123")

        # Verify
        assert result is False
        mock_connector.log.assert_called_with("No MFA factors found for user user123", level="warning")

    @pytest.mark.asyncio
    async def test_get_user_mfa_error(self, mock_connector, mock_okta_client):
        """Test MFA status retrieval with error."""
        # Setup
        mock_connector.client = mock_okta_client
        mock_okta_client.list_factors.return_value = (None, None, "API Error")

        # Execute
        result = await mock_connector.get_user_mfa("user123")

        # Verify
        assert result is False
        mock_connector.log.assert_called_with(
            "Error while fetching MFA status for user user123: API Error", level="warning"
        )

    @pytest.mark.asyncio
    async def test_next_list_users_success(self, mock_connector, mock_okta_client, sample_users_data):
        """Test successful user listing."""
        # Setup
        mock_connector.client = mock_okta_client
        mock_response = MagicMock()
        mock_response.has_next.return_value = False
        mock_okta_client.list_users.return_value = (sample_users_data, mock_response, None)

        # Execute
        result = [user async for user in mock_connector.next_list_users()]

        # Verify
        assert len(result) == 2
        assert result[0].id == "user1"
        assert result[1].id == "user2"
        mock_okta_client.list_users.assert_called_once()

    @pytest.mark.asyncio
    async def test_next_list_users_with_pagination(self, mock_connector, mock_okta_client, sample_users_data):
        """Test user listing with pagination."""
        # Setup
        mock_connector.client = mock_okta_client

        user3 = MagicMock()
        user3.id = "user3"
        user3.created = "2023-01-03T00:00:00.000Z"
        user3.profile.login = "user3@example.com"
        user3.profile.firstName = "User"
        user3.profile.lastName = "Three"
        user3.profile.email = "user3@example.com"

        mock_response = MagicMock()
        mock_response.has_next.return_value = True
        mock_response.next = AsyncMock(return_value=([user3], mock_response, None))

        mock_response_2 = MagicMock()
        mock_response_2.has_next.return_value = False
        mock_response.next.return_value = ([user3], mock_response_2, None)

        mock_okta_client.list_users.return_value = (sample_users_data, mock_response, None)

        # Execute
        result = [user async for user in mock_connector.next_list_users()]

        # Verify
        assert len(result) == 3
        assert result[2].id == "user3"
        mock_okta_client.list_users.assert_called_once()
        mock_response.next.assert_called_once()

    @pytest.mark.asyncio
    async def test_next_list_users_error(self, mock_connector, mock_okta_client):
        """Test user listing with error."""
        # Setup
        mock_connector.client = mock_okta_client
        mock_okta_client.list_users.return_value = (None, None, "API Error")

        # Execute
        result = [user async for user in mock_connector.next_list_users()]

        # Verify
        assert result == []
        mock_connector.log.assert_called_with("Error while listing users: API Error", level="error")

    @pytest.mark.asyncio
    async def test_next_list_users_no_users(self, mock_connector, mock_okta_client):
        """Test user listing when no users found."""
        # Setup
        mock_connector.client = mock_okta_client
        mock_response = MagicMock()
        mock_response.has_next.return_value = False
        mock_okta_client.list_users.return_value = ([], mock_response, None)

        # Execute
        result = [user async for user in mock_connector.next_list_users()]

        # Verify
        assert result == []

    @pytest.mark.asyncio
    async def test_map_fields_success(self, mock_connector, sample_user_data):
        """Test successful field mapping."""
        # Setup
        mock_connector.get_user_groups = AsyncMock(
            return_value=[Group(name="Test Group", uid="group1", desc="Test Description")]
        )
        mock_connector.get_user_mfa = AsyncMock(return_value=True)
        mock_connector.get_user_roles = AsyncMock(return_value=[])

        # Execute
        result = await mock_connector.map_fields(sample_user_data)

        # Verify
        assert isinstance(result, UserOCSFModel)
        assert result.user.uid == "user123"
        assert result.user.full_name == "Test User"
        assert result.user.email_addr == "test.user@example.com"
        assert result.user.name == "test.user@example.com"
        assert result.user.account.name == "test.user@example.com"
        assert result.user.account.uid == "user123"
        assert len(result.user.groups) == 1
        assert result.user.has_mfa is True
        # Verify new fields
        assert result.user.display_name == "Test User"
        assert result.user.domain == "example.com"
        assert result.user.uid_alt == "test.user@example.com"
        assert result.user.type_id is None  # No admin roles
        assert result.user.type is None
        assert result.activity_name == "Collect"
        assert result.category_name == "Discovery"
        assert result.class_name == "User Inventory Info"
        assert result.severity == "Informational"
        assert result.metadata.product.name == "Okta"
        assert result.metadata.product.vendor_name == "Okta"

    @pytest.mark.asyncio
    async def test_map_fields_with_empty_groups(self, mock_connector, sample_user_data):
        """Test field mapping with empty groups."""
        # Setup
        mock_connector.get_user_groups = AsyncMock(return_value=[])
        mock_connector.get_user_mfa = AsyncMock(return_value=False)
        mock_connector.get_user_roles = AsyncMock(return_value=[])

        # Execute
        result = await mock_connector.map_fields(sample_user_data)

        # Verify
        assert isinstance(result, UserOCSFModel)
        assert result.user.uid == "user123"
        assert len(result.user.groups) == 0
        assert result.user.has_mfa is False
        # Verify new fields are still populated
        assert result.user.display_name == "Test User"
        assert result.user.domain == "example.com"
        assert result.user.uid_alt == "test.user@example.com"

    @pytest.mark.asyncio
    async def test_get_assets_success(self, mock_connector, sample_users_data):
        """Test successful asset generation."""

        # Setup
        async def mock_next_list_users():
            for user in sample_users_data:
                yield user

        mock_connector.next_list_users = mock_next_list_users
        mock_mapped_asset1 = MagicMock()
        mock_mapped_asset2 = MagicMock()
        mock_connector.map_fields = AsyncMock(side_effect=[mock_mapped_asset1, mock_mapped_asset2])

        # Execute
        assets = [asset async for asset in mock_connector.get_assets()]

        # Verify
        assert len(assets) == 2
        assert assets[0] == mock_mapped_asset1
        assert assets[1] == mock_mapped_asset2
        mock_connector.log.assert_any_call("Starting Okta user assets generator", level="info")
        assert mock_connector.map_fields.call_count == 2

    @pytest.mark.asyncio
    async def test_get_assets_with_error(self, mock_connector, sample_users_data):
        """Test asset generation with mapping error."""

        # Setup
        async def mock_next_list_users():
            for user in sample_users_data:
                yield user

        mock_connector.next_list_users = mock_next_list_users
        mock_mapped_asset = MagicMock()
        # First call raises exception, second call succeeds
        mock_connector.map_fields = AsyncMock(side_effect=[Exception("Mapping error"), mock_mapped_asset])

        # Execute
        assets = [asset async for asset in mock_connector.get_assets()]

        # Verify
        assert len(assets) == 1  # Only one successful mapping
        assert assets[0] == mock_mapped_asset
        # Check that an error was logged
        error_calls = [
            call
            for call in mock_connector.log.call_args_list
            if call[0][0].startswith("Error while mapping user") and "Mapping error" in call[0][0]
        ]
        assert len(error_calls) > 0

    def test_most_recent_date_seen_property(self, mock_connector):
        """Test the most_recent_date_seen property."""
        # Setup
        mock_connector.context.__enter__.return_value = {"most_recent_date_seen": "2023-01-01T00:00:00.000Z"}

        # Execute
        result = mock_connector.most_recent_date_seen

        # Verify
        assert result == "2023-01-01T00:00:00.000Z"

    def test_most_recent_date_seen_none(self, mock_connector):
        """Test the most_recent_date_seen property when no date is set."""
        # Setup
        mock_connector.context.__enter__.return_value = {}

        # Execute
        result = mock_connector.most_recent_date_seen

        # Verify
        assert result is None

    def test_update_checkpoint_success(self, mock_connector):
        """Test successful checkpoint update."""
        # Setup
        mock_connector.new_most_recent_date = "2023-01-01T00:00:00.000Z"
        mock_cache: dict[str, str] = {}
        mock_connector.context.__enter__.return_value = mock_cache

        # Execute
        mock_connector.update_checkpoint()

        # Verify
        assert mock_cache["most_recent_date_seen"] == "2023-01-01T00:00:00.000Z"
        mock_connector.log.assert_called_with("Checkpoint updated with date: 2023-01-01T00:00:00.000Z", level="info")

    def test_update_checkpoint_none_date(self, mock_connector):
        """Test checkpoint update when new_most_recent_date is None."""
        # Setup
        mock_connector.new_most_recent_date = None

        # Execute
        mock_connector.update_checkpoint()

        # Verify
        mock_connector.log.assert_called_with(
            "Warning: new_most_recent_date is None, skipping checkpoint update", level="warning"
        )

    def test_update_checkpoint_error(self, mock_connector):
        """Test checkpoint update with error."""
        # Setup
        mock_connector.new_most_recent_date = "2023-01-01T00:00:00.000Z"
        mock_connector.context.__enter__.side_effect = Exception("Cache error")
        mock_connector._logger = MagicMock()  # Add missing _logger attribute
        mock_connector.log_exception = MagicMock()  # Mock log_exception method

        # Execute
        mock_connector.update_checkpoint()

        # Verify
        # Check that log was called with the error message
        error_calls = [
            call
            for call in mock_connector.log.call_args_list
            if call[0][0].startswith("Failed to update checkpoint: Cache error")
        ]
        assert len(error_calls) > 0
        mock_connector.log_exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_map_fields_with_none_values(self, mock_connector):
        """Test field mapping with None values in user profile."""
        # Setup
        user = MagicMock()
        user.id = "user123"
        user.created = "2023-01-01T00:00:00.000Z"
        user.profile.login = "test.user@example.com"
        user.profile.firstName = None
        user.profile.lastName = None
        user.profile.email = "test.user@example.com"
        # Explicitly set userType to None to prevent MagicMock default
        user.profile.userType = None

        mock_connector.get_user_groups = AsyncMock(return_value=[])
        mock_connector.get_user_mfa = AsyncMock(return_value=False)
        mock_connector.get_user_roles = AsyncMock(return_value=[])

        # Execute
        result = await mock_connector.map_fields(user)

        # Verify
        assert isinstance(result, UserOCSFModel)
        assert result.user.uid == "user123"
        assert result.user.full_name == "None None"  # None values converted to string
        assert result.user.email_addr == "test.user@example.com"
        assert result.user.name == "test.user@example.com"
        # Verify new fields with None displayName and userType
        assert result.user.display_name is None  # displayName not set
        assert result.user.domain == "example.com"
        assert result.user.uid_alt == "test.user@example.com"
        assert result.user.type_id is None  # No admin roles
        assert result.user.type is None

    @pytest.mark.asyncio
    async def test_map_fields_with_admin_user_type(self, mock_connector):
        """Test field mapping with admin user type."""
        # Setup
        user = MagicMock()
        user.id = "admin123"
        user.created = "2023-01-01T00:00:00.000Z"
        user.profile.login = "admin@example.com"
        user.profile.firstName = "Admin"
        user.profile.lastName = "User"
        user.profile.email = "admin@example.com"
        user.profile.displayName = "Admin User"
        user.profile.userType = "Administrator"

        # Mock an active admin role
        from okta.models.role_status import RoleStatus as OktaRoleStatus

        admin_role = MagicMock()
        admin_role.type = "SUPER_ADMIN"
        admin_role.status = OktaRoleStatus.ACTIVE

        mock_connector.get_user_groups = AsyncMock(return_value=[])
        mock_connector.get_user_mfa = AsyncMock(return_value=True)
        mock_connector.get_user_roles = AsyncMock(return_value=[admin_role])

        # Execute
        result = await mock_connector.map_fields(user)

        # Verify
        assert isinstance(result, UserOCSFModel)
        assert result.user.type_id == 2  # UserTypeId.ADMIN
        assert result.user.type == "Admin"  # UserTypeStr.ADMIN

    @pytest.mark.asyncio
    async def test_map_fields_with_system_user_type(self, mock_connector):
        """Test field mapping with non-admin role."""
        # Setup
        user = MagicMock()
        user.id = "user123"
        user.created = "2023-01-01T00:00:00.000Z"
        user.profile.login = "user@example.com"
        user.profile.firstName = "Regular"
        user.profile.lastName = "User"
        user.profile.email = "user@example.com"
        user.profile.displayName = "Regular User"

        # Mock a non-admin role
        from okta.models.role_status import RoleStatus as OktaRoleStatus

        user_role = MagicMock()
        user_role.type = "USER_ROLE"
        user_role.status = OktaRoleStatus.ACTIVE

        mock_connector.get_user_groups = AsyncMock(return_value=[])
        mock_connector.get_user_mfa = AsyncMock(return_value=False)
        mock_connector.get_user_roles = AsyncMock(return_value=[user_role])

        # Execute
        result = await mock_connector.map_fields(user)

        # Verify
        assert isinstance(result, UserOCSFModel)
        assert result.user.type_id is None  # Not an admin
        assert result.user.type is None

    @pytest.mark.asyncio
    async def test_map_fields_without_email_domain(self, mock_connector):
        """Test field mapping when email doesn't have domain."""
        # Setup
        user = MagicMock()
        user.id = "user123"
        user.created = "2023-01-01T00:00:00.000Z"
        user.profile.login = "testuser"
        user.profile.firstName = "Test"
        user.profile.lastName = "User"
        user.profile.email = None  # No email

        mock_connector.get_user_groups = AsyncMock(return_value=[])
        mock_connector.get_user_mfa = AsyncMock(return_value=False)
        mock_connector.get_user_roles = AsyncMock(return_value=[])

        # Execute
        result = await mock_connector.map_fields(user)

        # Verify
        assert isinstance(result, UserOCSFModel)
        assert result.user.domain is None  # No domain extracted

    @pytest.mark.asyncio
    async def test_map_fields_with_display_name_not_string(self, mock_connector):
        """Test field mapping when displayName is not a string (edge case)."""
        # Setup
        user = MagicMock()
        user.id = "user123"
        user.created = "2023-01-01T00:00:00.000Z"
        user.profile.login = "test@example.com"
        user.profile.firstName = "Test"
        user.profile.lastName = "User"
        user.profile.email = "test@example.com"
        # displayName is available but not a string (int in this case)
        user.profile.displayName = 12345

        mock_connector.get_user_groups = AsyncMock(return_value=[])
        mock_connector.get_user_mfa = AsyncMock(return_value=False)
        mock_connector.get_user_roles = AsyncMock(return_value=[])

        # Execute
        result = await mock_connector.map_fields(user)

        # Verify
        assert isinstance(result, UserOCSFModel)
        assert result.user.display_name is None  # Not set because it's not a string
