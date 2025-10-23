"""Unit tests for SentinelOneAssetClient."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
from sentinelone_module.asset_connector.client import SentinelOneAssetClient


@pytest.fixture
def client():
    """Create a test client instance."""
    return SentinelOneAssetClient(
        hostname="https://example.sentinelone.net",
        api_token="test_token",
        rate_limit_per_second=10,
    )


def test_client_initialization(client):
    """Test client initialization."""
    assert client.hostname == "example.sentinelone.net"
    assert client.api_token == "test_token"
    assert client.rate_limit_per_second == 10
    assert client.base_url == "https://example.sentinelone.net"
    assert client.session is not None


def test_session_headers(client):
    """Test that session has correct headers."""
    headers = client.session.headers
    assert headers["Authorization"] == "ApiToken test_token"
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"


def test_get_success(client):
    """Test successful GET request."""
    # Arrange
    mock_response = Mock()
    mock_response.json.return_value = {"data": [{"id": "123"}], "pagination": {"nextCursor": None}}
    mock_response.status_code = 200

    with patch.object(client.session, "get", return_value=mock_response) as mock_get:
        # Act
        result = client.get("/web/api/v2.1/agents", params={"limit": 100})

        # Assert
        assert result == {"data": [{"id": "123"}], "pagination": {"nextCursor": None}}
        mock_get.assert_called_once_with(
            "https://example.sentinelone.net/web/api/v2.1/agents", params={"limit": 100}, timeout=30
        )


def test_get_with_http_error(client):
    """Test GET request with HTTP error."""
    # Arrange
    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)

    with patch.object(client.session, "get", return_value=mock_response):
        # Act & Assert
        with pytest.raises(requests.exceptions.HTTPError):
            client.get("/web/api/v2.1/agents")


def test_get_with_request_exception(client):
    """Test GET request with request exception."""
    # Arrange
    with patch.object(client.session, "get", side_effect=requests.exceptions.RequestException("Connection error")):
        # Act & Assert
        with pytest.raises(requests.exceptions.RequestException):
            client.get("/web/api/v2.1/agents")


def test_limiter_adapter_configured(client):
    """Test that LimiterAdapter is properly configured."""
    # Check that the session has adapters mounted
    assert "https://" in client.session.adapters
    assert "http://" in client.session.adapters

    # The adapter should be a LimiterAdapter (from requests-ratelimiter)
    adapter = client.session.adapters["https://"]
    assert hasattr(adapter, "per_second") or adapter.__class__.__name__ == "LimiterAdapter"


def test_context_manager(client):
    """Test client can be used as context manager."""
    with patch.object(client, "close") as mock_close:
        with client as c:
            assert c is client
        mock_close.assert_called_once()


def test_close(client):
    """Test client close method."""
    mock_session = Mock()
    client.session = mock_session

    client.close()

    mock_session.close.assert_called_once()


def test_hostname_cleaning():
    """Test that hostname is cleaned properly."""
    # Test with https prefix
    client1 = SentinelOneAssetClient(
        hostname="https://test.sentinelone.net", api_token="token", rate_limit_per_second=10
    )
    assert client1.hostname == "test.sentinelone.net"

    # Test with http prefix
    client2 = SentinelOneAssetClient(
        hostname="http://test.sentinelone.net", api_token="token", rate_limit_per_second=10
    )
    assert client2.hostname == "test.sentinelone.net"

    # Test without prefix
    client3 = SentinelOneAssetClient(hostname="test.sentinelone.net", api_token="token", rate_limit_per_second=10)
    assert client3.hostname == "test.sentinelone.net"


def test_get_with_params(client):
    """Test GET request with query parameters."""
    # Arrange
    mock_response = Mock()
    mock_response.json.return_value = {"data": []}
    mock_response.status_code = 200

    with patch.object(client.session, "get", return_value=mock_response) as mock_get:
        # Act
        params = {"limit": 100, "cursor": "abc123", "createdAt__gt": "2024-01-01"}
        client.get("/web/api/v2.1/agents", params=params)

        # Assert
        mock_get.assert_called_once_with(
            "https://example.sentinelone.net/web/api/v2.1/agents", params=params, timeout=30
        )
