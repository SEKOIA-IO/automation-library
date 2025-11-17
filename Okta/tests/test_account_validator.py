from unittest.mock import Mock, PropertyMock, patch

from okta_modules.account_validator import OktaAccountValidator


class TestOktaAccountValidator:
    """Test cases for OktaAccountValidator class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_module = Mock()
        self.mock_module.configuration.base_url = "https://test.okta.com"
        self.mock_module.configuration.apikey = "test_api_key"
        self.validator = OktaAccountValidator(self.mock_module)

    def test_client_property_configuration(self):
        """Test that the client property returns a properly configured OktaClient."""
        with patch("okta_modules.account_validator.OktaClient") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            client = self.validator.client

            mock_client_class.assert_called_once_with({"orgUrl": "https://test.okta.com", "token": "test_api_key"})
            assert client == mock_client

    def test_validate_success_with_users(self):
        """Test successful validation when list_users() returns user data."""
        mock_client = Mock()
        # Mock the async list_users method to return some user data
        mock_users = [{"id": "1", "email": "test@example.com"}]

        async def mock_list_users():
            return mock_users

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            result = self.validator.validate()

            assert result is True

    def test_validate_connection_error(self):
        """Test validation failure when connection error occurs."""
        mock_client = Mock()

        # Mock the async list_users method to raise an exception
        async def mock_list_users():
            raise Exception("Connection failed")

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            with patch.object(self.validator, "log") as mock_log:
                result = self.validator.validate()

                assert result is False
                mock_log.assert_called_once_with("Error while validating account: Connection failed", level="error")

    def test_validate_authentication_error(self):
        """Test validation failure when authentication error occurs."""
        mock_client = Mock()

        # Mock the async list_users method to raise an authentication error
        async def mock_list_users():
            raise Exception("Invalid API key")

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            with patch.object(self.validator, "log") as mock_log:
                result = self.validator.validate()

                assert result is False
                mock_log.assert_called_once_with("Error while validating account: Invalid API key", level="error")

    def test_validate_success(self):
        """Test successful validation when list_users() completes without error."""
        mock_client = Mock()

        # Create a proper async mock
        async def mock_list_users():
            return []

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            result = self.validator.validate()

            assert result is True

    def test_validate_network_error(self):
        """Test validation failure when network error occurs."""
        mock_client = Mock()

        # Mock the async list_users method to raise a network error
        async def mock_list_users():
            raise Exception("Network timeout")

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            with patch.object(self.validator, "log") as mock_log:
                result = self.validator.validate()

                assert result is False
                mock_log.assert_called_once_with("Error while validating account: Network timeout", level="error")

    def test_validate_okta_specific_error(self):
        """Test validation failure when Okta-specific error occurs."""
        mock_client = Mock()

        # Mock the async list_users method to raise an Okta-specific error
        async def mock_list_users():
            raise Exception("Rate limit exceeded")

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            with patch.object(self.validator, "log") as mock_log:
                result = self.validator.validate()

                assert result is False
                mock_log.assert_called_once_with("Error while validating account: Rate limit exceeded", level="error")

    def test_validate_with_different_module_configurations(self):
        """Test validation with different module configurations."""
        # Test with different base URL
        different_mock_module = Mock()
        different_mock_module.configuration.base_url = "https://different.okta.com"
        different_mock_module.configuration.apikey = "different_api_key"

        with patch("okta_modules.account_validator.OktaClient") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            async def mock_list_users():
                return []

            mock_client.list_users = mock_list_users

            # Create new validator with different config
            validator = OktaAccountValidator(different_mock_module)
            result = validator.validate()

            assert result is True
            mock_client_class.assert_called_with(
                {"orgUrl": "https://different.okta.com", "token": "different_api_key"}
            )

    def test_validate_event_loop_handling(self):
        """Test that validate properly handles asyncio event loop."""
        mock_client = Mock()

        async def mock_list_users():
            return []

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            # Test that it works with existing event loop
            with patch("asyncio.get_event_loop") as mock_get_loop:
                mock_loop = Mock()
                mock_get_loop.return_value = mock_loop

                result = self.validator.validate()

                assert result is True
                mock_loop.run_until_complete.assert_called_once()

    def test_validate_logs_error_details(self):
        """Test that validation logs detailed error information."""
        mock_client = Mock()
        error_message = "Detailed error: HTTP 401 Unauthorized"

        async def mock_list_users():
            raise Exception(error_message)

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            with patch.object(self.validator, "log") as mock_log:
                result = self.validator.validate()

                assert result is False
                mock_log.assert_called_once_with(f"Error while validating account: {error_message}", level="error")
