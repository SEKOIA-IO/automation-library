from unittest.mock import patch, MagicMock, PropertyMock
import pytest
from googlethreatintelligence.scan_url import GTIScanURL

# === Test constants ===
API_KEY = "FAKE_API_KEY"
TEST_URL = "https://example.com/malware-test"


@patch("googlethreatintelligence.scan_url.vt.Client")
@patch("googlethreatintelligence.scan_url.VTAPIConnector")
def test_scan_url_success(mock_connector_class, mock_vt_client):
    """Test successful URL scan"""
    # Create mock connector instance
    mock_connector_instance = MagicMock()
    mock_connector_class.return_value = mock_connector_instance
    
    # Create mock analysis object with stats and results attributes
    mock_analysis = MagicMock()
    mock_analysis.stats = {"malicious": 5, "suspicious": 2, "harmless": 80}
    mock_analysis.results = {"Google Safebrowsing": "clean", "Kaspersky": "malware"}
    
    # Create mock result that will be in connector.results list
    mock_result = MagicMock()

    # /!\ A dict that matches what scan_url.py expects
    mock_result.response = {
    "analysis_stats": mock_analysis.stats,
    "analysis_results": mock_analysis.results,
    "url": TEST_URL
    }

    # Set up the results list to contain our mock result
    mock_connector_instance.results = [mock_result]
    
    # scan_url() doesn't return anything, it modifies results internally
    mock_connector_instance.scan_url.return_value = None

    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    # Run the action
    action = GTIScanURL()
    action.module.configuration = {"api_key": API_KEY}

    response = action.run({"url": TEST_URL})

    # Assertions
    assert response is not None
    assert isinstance(response, dict)
    assert response["success"] is True
    assert "data" in response
    assert response["data"]["analysis_stats"] == mock_analysis.stats
    assert response["data"]["analysis_results"] == mock_analysis.results
    assert response["data"]["url"] == TEST_URL

    # Verify mock calls
    mock_connector_class.assert_called_once_with(
        API_KEY,
        url=TEST_URL,
        domain="",
        ip="",
        file_hash="",
        cve=""
    )
    mock_vt_client.assert_called_once_with(API_KEY)
    mock_connector_instance.scan_url.assert_called_once_with(mock_client_instance)


@patch("googlethreatintelligence.scan_url.vt.Client")
@patch("googlethreatintelligence.scan_url.VTAPIConnector")
def test_scan_url_failure(mock_connector_class, mock_vt_client):
    """Test URL scan failure (no results in connector)"""
    # Create mock connector instance with empty results
    mock_connector_instance = MagicMock()
    mock_connector_class.return_value = mock_connector_instance
    
    # Empty results list simulates a failed scan
    mock_connector_instance.results = []
    mock_connector_instance.scan_url.return_value = None

    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    # Run the action
    action = GTIScanURL()
    action.module.configuration = {"api_key": API_KEY}

    response = action.run({"url": TEST_URL})

    # Assertions - should fail with IndexError when trying to access results[-1]
    assert response["success"] is False
    assert "error" in response
    # The actual error will be an IndexError: list index out of range

    # Verify mock calls
    mock_connector_class.assert_called_once_with(
        API_KEY,
        url=TEST_URL,
        domain="",
        ip="",
        file_hash="",
        cve=""
    )
    mock_connector_instance.scan_url.assert_called_once_with(mock_client_instance)


@patch("googlethreatintelligence.scan_url.vt.Client")
def test_scan_url_no_api_key(mock_vt_client):
    """Test missing API key"""
    action = GTIScanURL()
    with patch.object(type(action.module), "configuration", new_callable=PropertyMock) as mock_config:
        mock_config.return_value = {}

        response = action.run({"url": TEST_URL})

        assert response["success"] is False
        assert "API key" in response["error"]

        mock_vt_client.assert_not_called()


@patch("googlethreatintelligence.scan_url.vt.Client")
def test_scan_url_no_url_provided(mock_vt_client):
    """Test missing URL in arguments"""
    action = GTIScanURL()
    action.module.configuration = {"api_key": API_KEY}

    response = action.run({})

    assert response["success"] is False
    assert "No URL provided" in response["error"]

    mock_vt_client.assert_not_called()


@patch("googlethreatintelligence.scan_url.vt.Client")
@patch("googlethreatintelligence.scan_url.VTAPIConnector")
def test_scan_url_exception(mock_connector_class, mock_vt_client):
    """Test exception handling"""
    # Create mock connector instance that raises exception
    mock_connector_instance = MagicMock()
    mock_connector_class.return_value = mock_connector_instance
    mock_connector_instance.scan_url.side_effect = Exception("Unexpected Error")

    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    # Run the action
    action = GTIScanURL()
    action.module.configuration = {"api_key": API_KEY}

    response = action.run({"url": TEST_URL})

    # Assertions
    assert response["success"] is False
    assert "Unexpected Error" in response["error"]

    # Verify mock calls
    mock_connector_class.assert_called_once()
    mock_connector_instance.scan_url.assert_called_once_with(mock_client_instance)


@patch("googlethreatintelligence.scan_url.vt.Client")
@patch("googlethreatintelligence.scan_url.VTAPIConnector")
def test_scan_url_api_error(mock_connector_class, mock_vt_client):
    """Test VT API error handling"""
    # Create mock connector instance
    mock_connector_instance = MagicMock()
    mock_connector_class.return_value = mock_connector_instance
    
    # Simulate API error by having scan_url not add results
    # (based on client.py, scan_url catches vt.APIError and returns None)
    mock_connector_instance.results = []
    mock_connector_instance.scan_url.return_value = None

    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    # Run the action
    action = GTIScanURL()
    action.module.configuration = {"api_key": API_KEY}

    response = action.run({"url": TEST_URL})

    # Assertions - should fail when accessing empty results list
    assert response["success"] is False
    assert "error" in response