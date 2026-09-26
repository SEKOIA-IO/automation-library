import pytest
from unittest.mock import MagicMock, patch
from googlethreatintelligence.client import VTAPIConnector

API_KEY = "FAKE_API_KEY"


@pytest.mark.parametrize(
    "entity_type, entity, report_method",
    [
        ("ip_addresses", "8.8.8.8", "get_ip_report"),
        ("domains", "google.com", "get_domain_report"),
        ("urls", "https://example.com", "get_url_report"),
        ("files", "44d88612fea8a8f36de82e1278abb02f", "get_file_report"),
    ],
)
def test_ioc_reports_success(mock_vt_client, entity_type, entity, report_method):
    """Test generic IOC report methods success"""

    connector = VTAPIConnector(api_key=API_KEY)

    # Mock get_object to return a custom object
    mock_obj = MagicMock()
    mock_obj.id = entity
    mock_obj.reputation = 100
    mock_obj.last_analysis_stats = {"malicious": 0, "suspicious": 0, "clean": 80}

    mock_vt_client.get_object.return_value = mock_obj

    # Call specific report method dynamically
    getattr(connector, report_method)(mock_vt_client)

    # Validate results
    assert len(connector.results) == 1
    result = connector.results[0]
    assert result.status == "SUCCESS"
    assert result.response["entity_type"] == entity_type


def test_ioc_report_without_optional_attributes(mock_vt_client):
    """Test get_ioc_report when object lacks country, categories, last_analysis_stats."""
    connector = VTAPIConnector(api_key=API_KEY)

    mock_obj = MagicMock(spec=[])  # no attributes by default
    mock_obj.id = "test-id"
    mock_obj.reputation = 50

    mock_vt_client.get_object.return_value = mock_obj

    connector.get_ioc_report(mock_vt_client, "domains", "example.com")

    result = connector.results[0]
    assert result.status == "SUCCESS"
    assert "last_analysis_stats" not in result.response
    assert "country" not in result.response
    assert "categories" not in result.response


def test_ioc_report_with_none_categories(mock_vt_client):
    """Test get_ioc_report with categories=None."""
    connector = VTAPIConnector(api_key=API_KEY)

    mock_obj = MagicMock()
    mock_obj.id = "test-id"
    mock_obj.reputation = 50
    mock_obj.last_analysis_stats = {"malicious": 0}
    mock_obj.country = "US"
    mock_obj.categories = None

    mock_vt_client.get_object.return_value = mock_obj

    connector.get_ioc_report(mock_vt_client, "ip_addresses", "1.2.3.4")

    result = connector.results[0]
    assert result.status == "SUCCESS"
    assert result.response["country"] == "US"
    assert result.response["categories"] is None


def test_ioc_report_api_error(mock_vt_client):
    """Test get_ioc_report handles APIError"""
    connector = VTAPIConnector(api_key=API_KEY)
    from vt import APIError

    mock_vt_client.get_object.side_effect = APIError("FailedError", "FakeError")

    connector.get_ioc_report(mock_vt_client, "domains", "google.com")

    result = connector.results[0]
    assert result.status == "ERROR"
    assert "FakeError" in result.error
