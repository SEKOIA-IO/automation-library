import asyncio
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
        mock_users = [{"id": "1", "email": "test@example.com"}]

        async def mock_list_users():
            return mock_users, Mock(), None

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            result = self.validator.validate()

            assert result is True

    def test_validate_connection_error(self):
        """Test validation failure when connection error is raised."""
        mock_client = Mock()

        async def mock_list_users():
            raise Exception("Connection failed")

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            with patch.object(self.validator, "log") as mock_log:
                result = self.validator.validate()

                assert result is False
                mock_log.assert_called_once_with(
                    "Error while validating account. Authentication failed: Connection failed", level="error"
                )

    def test_validate_authentication_error_from_sdk_tuple(self):
        """Okta SDK returns (None, resp, error) on 401 — validator must detect it."""
        mock_client = Mock()
        okta_error = Mock()
        okta_error.message = "Okta HTTP 401 E0000011 Invalid token provided"

        async def mock_list_users():
            return None, Mock(), okta_error

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            with patch.object(self.validator, "log") as mock_log:
                with patch.object(self.validator, "error") as mock_error:
                    result = self.validator.validate()

                    assert result is False
                    mock_log.assert_called_once_with(
                        f"Error while validating account. Authentication failed: {okta_error.message}", level="error"
                    )

    def test_validate_error_without_message_attribute(self):
        """Validator falls back to str(err) when the error has no message attribute."""
        mock_client = Mock()

        async def mock_list_users():
            return None, Mock(), "raw string error"

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            with patch.object(self.validator, "log") as mock_log:
                result = self.validator.validate()

                assert result is False
                mock_log.assert_called_once_with(
                    "Error while validating account. Authentication failed: raw string error", level="error"
                )

    def test_validate_success(self):
        """Test successful validation when list_users() completes without error."""
        mock_client = Mock()

        async def mock_list_users():
            return [], Mock(), None

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            result = self.validator.validate()

            assert result is True

    def test_validate_network_error(self):
        """Test validation failure when network error is raised."""
        mock_client = Mock()

        async def mock_list_users():
            raise Exception("Network timeout")

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            with patch.object(self.validator, "log") as mock_log:
                result = self.validator.validate()

                assert result is False
                mock_log.assert_called_once_with(
                    "Error while validating account. Authentication failed: Network timeout", level="error"
                )

    def test_validate_with_different_module_configurations(self):
        """Test validation with different module configurations."""
        different_mock_module = Mock()
        different_mock_module.configuration.base_url = "https://different.okta.com"
        different_mock_module.configuration.apikey = "different_api_key"

        with patch("okta_modules.account_validator.OktaClient") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            async def mock_list_users():
                return [], Mock(), None

            mock_client.list_users = mock_list_users

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
            return [], Mock(), None

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            with patch("asyncio.get_event_loop") as mock_get_loop:
                mock_loop = Mock()
                mock_loop.run_until_complete.return_value = ([], Mock(), None)
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
                mock_log.assert_called_once_with(
                    f"Error while validating account. Authentication failed: {error_message}", level="error"
                )

    def test_validate_error_with_empty_message_falls_back_to_str(self):
        """Okta errors carrying an empty `.message` must not produce a blank log/error."""
        mock_client = Mock()

        class FakeOktaError:
            message = ""

            def __str__(self):
                return "Your Okta domain should not contain -admin."

        okta_error = FakeOktaError()

        async def mock_list_users():
            return None, Mock(), okta_error

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            with patch.object(self.validator, "log") as mock_log:
                with patch.object(self.validator, "error") as mock_error:
                    result = self.validator.validate()

                    assert result is False
                    expected = (
                        "Error while validating account. Authentication failed: "
                        "Your Okta domain should not contain -admin."
                    )
                    mock_log.assert_called_once_with(expected, level="error")
                    mock_error.assert_called_once_with(expected)

    def test_validate_error_with_empty_message_and_empty_str_falls_back_to_repr(self):
        """Errors that stringify to an empty string (e.g. TimeoutError) still yield a message."""
        mock_client = Mock()
        okta_error = asyncio.TimeoutError()

        async def mock_list_users():
            return None, Mock(), okta_error

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            with patch.object(self.validator, "log") as mock_log:
                with patch.object(self.validator, "error") as mock_error:
                    result = self.validator.validate()

                    assert result is False
                    expected = "Error while validating account. Authentication failed: TimeoutError()"
                    mock_log.assert_called_once_with(expected, level="error")
                    mock_error.assert_called_once_with(expected)

    def test_validate_reports_error_to_platform_on_sdk_error(self):
        """`error()` must be called so the platform shows the real message, not "Unknown error"."""
        mock_client = Mock()
        okta_error = Mock()
        okta_error.message = "Okta HTTP 401 E0000011 Invalid token provided"

        async def mock_list_users():
            return None, Mock(), okta_error

        mock_client.list_users = mock_list_users

        with patch.object(type(self.validator), "client", new_callable=PropertyMock, return_value=mock_client):
            with patch.object(self.validator, "error") as mock_error:
                result = self.validator.validate()

                assert result is False
                mock_error.assert_called_once_with(
                    f"Error while validating account. Authentication failed: {okta_error.message}"
                )

    def test_validate_reports_error_to_platform_on_exception(self):
        """Client construction failures (e.g. a `-admin` org URL) must reach the platform too."""
        with patch.object(
            type(self.validator),
            "client",
            new_callable=PropertyMock,
            side_effect=ValueError("Your Okta domain should not contain -admin."),
        ):
            with patch.object(self.validator, "log") as mock_log:
                with patch.object(self.validator, "error") as mock_error:
                    result = self.validator.validate()

                    assert result is False
                    expected = (
                        "Error while validating account. Authentication failed: "
                        "Your Okta domain should not contain -admin."
                    )
                    mock_log.assert_called_once_with(expected, level="error")
                    mock_error.assert_called_once_with(expected)
