"""
Unit tests for GTIGetPassiveDNS Action
"""

from unittest.mock import patch, MagicMock, PropertyMock
import vt
from googlethreatintelligence.get_passive_dns import GTIGetPassiveDNS

# === Test constants ===
API_KEY = "FAKE_API_KEY"
DOMAIN = "google.com"


@patch("googlethreatintelligence.get_passive_dns.vt.Client")
def test_get_passive_dns_success(mock_vt_client):
    """Test successful retrieval of passive DNS data"""
    # Create fake resolution objects
    mock_resolution_1 = MagicMock()
    mock_resolution_1.ip_address = "8.8.8.8"
    mock_resolution_1.host_name = DOMAIN
    mock_resolution_1.date = "2024-10-15 12:00:00"
    mock_resolution_1.resolver = "resolver1"

    mock_resolution_2 = MagicMock()
    mock_resolution_2.ip_address = "8.8.4.4"
    mock_resolution_2.host_name = DOMAIN
    mock_resolution_2.date = "2024-10-15 12:05:00"
    mock_resolution_2.resolver = "resolver2"

    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    # Mock iterator() to return our fake DNS resolutions
    mock_client_instance.iterator.return_value = iter([mock_resolution_1, mock_resolution_2])

    # Setup the action
    action = GTIGetPassiveDNS()
    action.module.configuration = {"api_key": API_KEY}

    # Execute the action
    response = action.run({"domain": DOMAIN})

    # === Assertions ===
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is True
    assert "data" in response
    data = response["data"]

    assert data["resolutions_count"] == 2
    assert data["unique_ips_count"] == 2
    assert "8.8.8.8" in data["unique_ips"]
    assert "8.8.4.4" in data["unique_ips"]
    assert len(data["resolutions"]) == 2
    assert data["resolutions"][0]["ip_address"] == "8.8.8.8"

    # Verify vt.Client was instantiated with the correct API key
    mock_vt_client.assert_called_once_with(API_KEY)

    # Verify iterator was called with correct endpoint and limit
    mock_client_instance.iterator.assert_called_once_with(
        f"/domains/{DOMAIN}/resolutions",
        limit=40
    )


@patch("googlethreatintelligence.get_passive_dns.vt.Client")
def test_get_passive_dns_fail(mock_vt_client):
    """Test failure when VirusTotal API raises an exception"""
    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    # Simulate API error
    mock_client_instance.iterator.side_effect = vt.APIError("QuotaExceededError", "Rate limit exceeded")

    # Setup the action
    action = GTIGetPassiveDNS()
    action.module.configuration = {"api_key": API_KEY}

    # Execute the action
    response = action.run({"domain": DOMAIN})

    # === Assertions ===
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is False
    assert "error" in response
    assert "Rate limit exceeded" in response["error"]

    # Ensure vt.Client was called
    mock_vt_client.assert_called_once_with(API_KEY)


def test_get_passive_dns_no_api_key():
    """Test missing API key handling"""
    action = GTIGetPassiveDNS()

    # Patch the configuration property to simulate missing key
    with patch.object(type(action.module), "configuration", new_callable=PropertyMock) as mock_config:
        mock_config.return_value = {}

        response = action.run({"domain": DOMAIN})

        # === Assertions ===
        assert response is not None
        assert isinstance(response, dict)
        assert response.get("success") is False
        assert "API key" in response.get("error", "")
