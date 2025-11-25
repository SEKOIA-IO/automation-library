from unittest.mock import AsyncMock, Mock, patch

import pytest
from sekoia_automation.module import Module

from azure_ad.account_validator import AzureADAccountValidator


@pytest.fixture
def test_azure_ad_account_validator(symphony_storage):
    module = Module()
    module_configuration: dict = {
        "tenant_id": "fake_tenant_id",
        "client_id": "fake_client_id",
        "client_secret": "fake_client_secret",
    }
    module.configuration = module_configuration

    validator = AzureADAccountValidator(module=module, data_path=symphony_storage)
    validator.error = Mock()

    yield validator


def test_configuration(test_azure_ad_account_validator):
    """Test that the validator has the correct configuration."""
    assert test_azure_ad_account_validator.module.configuration["tenant_id"] == "fake_tenant_id"
    assert test_azure_ad_account_validator.module.configuration["client_id"] == "fake_client_id"
    assert test_azure_ad_account_validator.module.configuration["client_secret"] == "fake_client_secret"


@patch("azure_ad.account_validator.asyncio.get_event_loop")
def test_validate_success(mock_get_event_loop, test_azure_ad_account_validator):
    """Test that validate returns True when the API call succeeds."""
    # Arrange
    mock_loop = Mock()
    mock_get_event_loop.return_value = mock_loop

    # Mock the GraphApi client and its client property
    mock_graph_api = Mock()
    mock_graph_service_client = Mock()
    mock_users = Mock()
    mock_users.get = AsyncMock()
    mock_graph_service_client.users = mock_users
    mock_graph_api.client = mock_graph_service_client
    test_azure_ad_account_validator._client = mock_graph_api

    # Act
    result = test_azure_ad_account_validator.validate()

    # Assert
    assert result is True
    mock_loop.run_until_complete.assert_called_once()
    test_azure_ad_account_validator.error.assert_not_called()


@patch("azure_ad.account_validator.asyncio.get_event_loop")
def test_validate_failure_connection_error(mock_get_event_loop, test_azure_ad_account_validator):
    """Test that validate returns False when there's a connection error."""
    # Arrange
    mock_loop = Mock()
    mock_get_event_loop.return_value = mock_loop

    # Mock the GraphApi client and its client property
    mock_graph_api = Mock()
    mock_graph_service_client = Mock()
    mock_users = Mock()
    mock_users.get = AsyncMock(side_effect=Exception("Connection failed"))
    mock_graph_service_client.users = mock_users
    mock_graph_api.client = mock_graph_service_client
    test_azure_ad_account_validator._client = mock_graph_api

    # Configure run_until_complete to raise the exception
    mock_loop.run_until_complete.side_effect = Exception("Connection failed")

    # Act
    result = test_azure_ad_account_validator.validate()

    # Assert
    assert result is False
    test_azure_ad_account_validator.error.assert_called_once_with(
        "Impossible to connect to the Azure AD tenant: Connection failed"
    )


@patch("azure_ad.account_validator.asyncio.get_event_loop")
def test_validate_failure_authentication_error(mock_get_event_loop, test_azure_ad_account_validator):
    """Test that validate returns False when there's an authentication error."""
    # Arrange
    mock_loop = Mock()
    mock_get_event_loop.return_value = mock_loop

    # Mock the GraphApi client and its client property
    mock_graph_api = Mock()
    mock_graph_service_client = Mock()
    mock_users = Mock()
    mock_users.get = AsyncMock(side_effect=Exception("Invalid credentials"))
    mock_graph_service_client.users = mock_users
    mock_graph_api.client = mock_graph_service_client
    test_azure_ad_account_validator._client = mock_graph_api

    # Configure run_until_complete to raise the exception
    mock_loop.run_until_complete.side_effect = Exception("Invalid credentials")

    # Act
    result = test_azure_ad_account_validator.validate()

    # Assert
    assert result is False
    test_azure_ad_account_validator.error.assert_called_once_with(
        "Impossible to connect to the Azure AD tenant: Invalid credentials"
    )


@patch("azure_ad.account_validator.asyncio.get_event_loop")
def test_validate_failure_network_error(mock_get_event_loop, test_azure_ad_account_validator):
    """Test that validate returns False when there's a network error."""
    # Arrange
    mock_loop = Mock()
    mock_get_event_loop.return_value = mock_loop

    # Mock the GraphApi client and its client property
    mock_graph_api = Mock()
    mock_graph_service_client = Mock()
    mock_users = Mock()
    mock_users.get = AsyncMock(side_effect=Exception("Network timeout"))
    mock_graph_service_client.users = mock_users
    mock_graph_api.client = mock_graph_service_client
    test_azure_ad_account_validator._client = mock_graph_api

    # Configure run_until_complete to raise the exception
    mock_loop.run_until_complete.side_effect = Exception("Network timeout")

    # Act
    result = test_azure_ad_account_validator.validate()

    # Assert
    assert result is False
    test_azure_ad_account_validator.error.assert_called_once_with(
        "Impossible to connect to the Azure AD tenant: Network timeout"
    )


@patch("azure_ad.account_validator.asyncio.get_event_loop")
def test_validate_uses_cached_client(mock_get_event_loop, test_azure_ad_account_validator):
    """Test that validate uses the cached client property."""
    # Arrange
    mock_loop = Mock()
    mock_get_event_loop.return_value = mock_loop

    # Mock the GraphApi client and its client property
    mock_graph_api = Mock()
    mock_graph_service_client = Mock()
    mock_users = Mock()
    mock_users.get = AsyncMock()
    mock_graph_service_client.users = mock_users
    mock_graph_api.client = mock_graph_service_client

    # Set the cached client directly
    test_azure_ad_account_validator._client = mock_graph_api

    # Act
    result = test_azure_ad_account_validator.validate()

    # Assert
    assert result is True
    mock_users.get.assert_called_once()
    test_azure_ad_account_validator.error.assert_not_called()
