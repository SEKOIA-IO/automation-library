"""Tests for client.py get_passive_dns edge cases."""

from unittest.mock import MagicMock
import vt
from googlethreatintelligence.client import VTAPIConnector


def test_passive_dns_resolution_without_ip(mock_vt_client):
    """Test resolution with no ip_address attribute skips unique_ips tracking (L533)."""
    connector = VTAPIConnector(api_key="k", domain="example.com")

    r1 = MagicMock()
    r1.ip_address = None
    r1.host_name = "example.com"
    r1.date = "2024-01-01"
    r1.resolver = "r1"

    r2 = MagicMock()
    r2.ip_address = "1.2.3.4"
    r2.host_name = "example.com"
    r2.date = "2024-01-02"
    r2.resolver = "r2"

    mock_vt_client.iterator.return_value = iter([r1, r2])

    connector.get_passive_dns(mock_vt_client)

    result = connector.results[-1]
    assert result.status == "SUCCESS"
    assert result.response["resolutions_count"] == 2
    assert result.response["unique_ips_count"] == 1
    assert "1.2.3.4" in result.response["unique_ips"]


def test_passive_dns_api_error(mock_vt_client):
    """Test get_passive_dns handles APIError."""
    connector = VTAPIConnector(api_key="k", domain="fail.com")

    mock_vt_client.iterator.side_effect = vt.APIError("PremiumError", "Requires Premium")

    connector.get_passive_dns(mock_vt_client)

    result = connector.results[-1]
    assert result.status == "NOT_AVAILABLE"
    assert "Premium API" in result.error
