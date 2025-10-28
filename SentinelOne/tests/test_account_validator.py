"""Unit tests for SentinelOneAccountValidator."""

import pytest
from unittest.mock import Mock, patch, PropertyMock

from sentinelone_module.account_validator import SentinelOneAccountValidator
from sentinelone_module.base import SentinelOneModule


@pytest.fixture
def account_validator(symphony_storage):
    """Create a test SentinelOne account validator."""
    module = SentinelOneModule()
    module.configuration = {
        "hostname": "https://example.sentinelone.net",
        "api_token": "fake_sentinelone_api_key",
    }
    validator = SentinelOneAccountValidator(module=module, data_path=symphony_storage)
    return validator


@pytest.fixture
def mock_client():
    """Create a mock SentinelOne client."""
    return Mock()


def test_account_validator_init(account_validator):
    """Test that account validator initializes correctly."""
    assert account_validator is not None
    assert account_validator.module is not None


def test_account_validator_client_property(account_validator):
    """Test the client property returns a configured SentinelOne client."""
    # Access the client (should be a SentinelOneClient instance)
    client = account_validator.client

    # Verify it's a SentinelOneClient with expected configuration
    # Note: clean_hostname removes the protocol prefix
    assert client.hostname == "example.sentinelone.net"
    assert client.api_token == "fake_sentinelone_api_key"
    assert client.rate_limit_per_second == 10


def test_validate_success(account_validator, mock_client):
    """Test successful account validation."""
    # Arrange
    mock_client.get.return_value = {"data": {"count": 100}}

    with patch.object(type(account_validator), "client", new_callable=PropertyMock) as mock_client_prop:
        mock_client_prop.return_value = mock_client

        # Act
        result = account_validator.validate()

        # Assert
        assert result is True
        mock_client.get.assert_called_once_with("/web/api/v2.1/agents/count", params={})


def test_validate_api_error_response(account_validator, mock_client):
    """Test validation with API error response."""
    # Arrange
    mock_client.get.return_value = {"error": "Invalid API token"}

    with patch.object(type(account_validator), "client", new_callable=PropertyMock) as mock_client_prop:
        mock_client_prop.return_value = mock_client

        # Act
        result = account_validator.validate()

        # Assert
        assert result is False
        mock_client.get.assert_called_once_with("/web/api/v2.1/agents/count", params={})


def test_validate_missing_data(account_validator, mock_client):
    """Test validation when response is missing data field."""
    # Arrange
    mock_client.get.return_value = {"pagination": {"totalItems": 0}}

    with patch.object(type(account_validator), "client", new_callable=PropertyMock) as mock_client_prop:
        mock_client_prop.return_value = mock_client

        # Act
        result = account_validator.validate()

        # Assert
        assert result is False


def test_validate_exception_handling(account_validator, mock_client):
    """Test validation when an exception is raised."""
    # Arrange
    mock_client.get.side_effect = Exception("Connection error")

    with patch.object(type(account_validator), "client", new_callable=PropertyMock) as mock_client_prop:
        mock_client_prop.return_value = mock_client

        # Act
        result = account_validator.validate()

        # Assert
        assert result is False


def test_validate_network_timeout(account_validator, mock_client):
    """Test validation when network timeout occurs."""
    # Arrange
    mock_client.get.side_effect = TimeoutError("Request timed out")

    with patch.object(type(account_validator), "client", new_callable=PropertyMock) as mock_client_prop:
        mock_client_prop.return_value = mock_client

        # Act
        result = account_validator.validate()

        # Assert
        assert result is False


def test_validate_with_different_success_response(account_validator, mock_client):
    """Test validation with different successful response format."""
    # Arrange
    mock_client.get.return_value = {"data": {"count": 250, "siteIds": ["site1", "site2"]}}

    with patch.object(type(account_validator), "client", new_callable=PropertyMock) as mock_client_prop:
        mock_client_prop.return_value = mock_client

        # Act
        result = account_validator.validate()

        # Assert
        assert result is True


def test_validate_empty_data(account_validator, mock_client):
    """Test validation when data field exists but is empty."""
    # Arrange
    mock_client.get.return_value = {"data": {}}

    with patch.object(type(account_validator), "client", new_callable=PropertyMock) as mock_client_prop:
        mock_client_prop.return_value = mock_client

        # Act
        result = account_validator.validate()

        # Assert
        assert result is True  # data field exists, so validation passes
