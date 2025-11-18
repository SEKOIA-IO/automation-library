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
    mock_connector_instance = MagicMock()
    mock_connector_class.return_value = mock_connector_instance
    mock_connector_instance.scan_url.return_value = "analysis_1234"

    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    action = GTIScanURL()
    action.module.configuration = {"api_key": API_KEY}

    response = action.run({"url": TEST_URL})

    assert response is not None
    assert isinstance(response, dict)
    assert response["success"] is True
    assert response["data"] == "analysis_1234"

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
    """Test URL scan failure (no analysis returned)"""
    mock_connector_instance = MagicMock()
    mock_connector_class.return_value = mock_connector_instance
    mock_connector_instance.scan_url.return_value = None

    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    action = GTIScanURL()
    action.module.configuration = {"api_key": API_KEY}

    response = action.run({"url": TEST_URL})

    assert response["success"] is False
    assert "URL scan failed" in response["error"]

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
    mock_connector_instance = MagicMock()
    mock_connector_class.return_value = mock_connector_instance
    mock_connector_instance.scan_url.side_effect = Exception("Unexpected Error")

    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    action = GTIScanURL()
    action.module.configuration = {"api_key": API_KEY}

    response = action.run({"url": TEST_URL})

    assert response["success"] is False
    assert "Unexpected Error" in response["error"]

    mock_connector_class.assert_called_once()
    mock_connector_instance.scan_url.assert_called_once_with(mock_client_instance)
