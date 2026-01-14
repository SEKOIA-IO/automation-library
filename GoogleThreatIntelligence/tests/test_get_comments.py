import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import vt

from googlethreatintelligence.get_comments import GTIGetComments


API_KEY = "FAKE_API_KEY"


# =============================================================================
# Helpers
# =============================================================================


def mock_comment():
    c = MagicMock()
    c.text = "Test comment"
    c.date = "2021-09-05 10:30:31"
    c.votes = {"positive": 5, "negative": 1}
    c.author = "test_user"
    return c


def assert_success(response):
    assert isinstance(response, dict)
    assert response.get("success") is True
    assert "data" in response
    assert response["data"]["comments_count"] == 1
    assert isinstance(response["data"]["entity"], str)
    assert response["data"]["comments"][0]["text"] == "Test comment"


def assert_iterator_called(mock_client):
    mock_client.iterator.assert_called_once()
    args, kwargs = mock_client.iterator.call_args
    assert args[0].endswith("/comments")
    assert kwargs.get("limit") == 10


# =============================================================================
# Routing tests based on REAL action behavior
# =============================================================================


@pytest.mark.parametrize(
    "ioc_field,ioc_value,expected_prefix",
    [
        ("domain", "google.com", "/domains/"),  # resolved to IP internally
        ("ip", "8.8.8.8", "/ip_addresses/"),
        ("url", "http://example.com", "/urls/"),
        ("file_hash", "44d88612fea8a8f36de82e1278abb02f", "/files/"),
    ],
)
@patch("googlethreatintelligence.get_comments.vt.Client")
def test_get_comments_routing(mock_vt_client, ioc_field, ioc_value, expected_prefix):

    mock_client = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client
    mock_client.iterator.return_value = iter([mock_comment()])

    action = GTIGetComments()
    action.module.configuration = {"api_key": API_KEY}

    payload = {ioc_field: ioc_value}

    response = action.run(payload)
    assert_success(response)

    mock_client.iterator.assert_called_once()
    args, _ = mock_client.iterator.call_args
    path = args[0]

    # MATCH THE REAL PREFIX
    assert path.startswith(expected_prefix)
    assert path.endswith("/comments")


# =============================================================================
# API error scenario
# =============================================================================


@patch("googlethreatintelligence.get_comments.vt.Client")
def test_get_comments_fail(mock_vt_client):

    mock_client = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client

    mock_client.iterator.side_effect = vt.APIError("WrongCredentialsError", "Invalid API key")

    action = GTIGetComments()
    action.module.configuration = {"api_key": API_KEY}

    response = action.run({"domain": "google.com"})

    assert isinstance(response, dict)
    assert response.get("success") is False
    assert response.get("data") is None  # REAL behavior
    assert "Invalid API key" in response.get("error", "")


# =============================================================================
# Missing API key
# =============================================================================


def test_get_comments_missing_api_key():
    action = GTIGetComments()

    with patch.object(type(action.module), "configuration", new_callable=PropertyMock) as mock_config:
        mock_config.return_value = {}

        response = action.run({"domain": "google.com"})

        assert isinstance(response, dict)
        assert response.get("success") is False
        assert "API key" in response.get("error", "")
