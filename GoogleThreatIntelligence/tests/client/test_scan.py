import pytest
from unittest.mock import MagicMock
from googlethreatintelligence.client import VTAPIConnector

API_KEY = "FAKE_API_KEY"


def test_scan_url_success(mock_vt_client):
    connector = VTAPIConnector(api_key=API_KEY)
    mock_analysis = MagicMock()
    mock_analysis.stats = {"malicious": 5}
    mock_analysis.results = {"scanner": "clean"}

    mock_vt_client.scan_url.return_value = mock_analysis

    connector.scan_url(mock_vt_client)

    result = connector.results[0]
    assert result.status == "SUCCESS"
    assert result.response["analysis_stats"] == {"malicious": 5}


def test_scan_url_api_error(mock_vt_client):
    from vt import APIError

    connector = VTAPIConnector(api_key=API_KEY)
    mock_vt_client.scan_url.side_effect = APIError("FailedError", "API failed")

    connector.scan_url(mock_vt_client)
    result = connector.results[0]
    assert result.status == "ERROR"
    assert "API failed" in result.error


def test_scan_file_success(mock_vt_client, fake_file):
    connector = VTAPIConnector(api_key=API_KEY)
    mock_analysis = MagicMock()
    mock_analysis.stats = {"malicious": 0}
    mock_analysis.results = {"scanner": "clean"}

    mock_vt_client.scan_file.return_value = mock_analysis

    connector.scan_file(mock_vt_client, fake_file)
    result = connector.results[0]
    assert result.status == "SUCCESS"
    assert result.response["file_path"] == fake_file


def test_scan_file_not_found(mock_vt_client):
    connector = VTAPIConnector(api_key=API_KEY)
    connector.scan_file(mock_vt_client, "/nonexistent/path.txt")
    result = connector.results[0]
    assert result.status == "ERROR"
    assert "File not found" in result.error


def test_scan_file_api_error(mock_vt_client, fake_file):
    from vt import APIError

    connector = VTAPIConnector(api_key=API_KEY)
    mock_vt_client.scan_file.side_effect = APIError("FailedError", "Scan failed")
    connector.scan_file(mock_vt_client, fake_file)
    result = connector.results[0]
    assert result.status == "ERROR"
    assert "Scan failed" in result.error
