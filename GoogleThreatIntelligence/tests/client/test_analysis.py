import pytest
from unittest.mock import MagicMock
from googlethreatintelligence.client import VTAPIConnector

API_KEY = "FAKE_API_KEY"


def test_get_analysis_success(mock_vt_client):
    connector = VTAPIConnector(api_key=API_KEY)
    mock_analysis = MagicMock()
    mock_analysis.status = "completed"
    mock_analysis.stats = {"malicious": 1}
    mock_vt_client.get_object.return_value = mock_analysis

    connector.get_analysis(mock_vt_client, "analysis_id")
    result = connector.results[0]
    assert result.status == "SUCCESS"
    assert result.response["status"] == "completed"


def test_get_analysis_api_error(mock_vt_client):
    from vt import APIError

    connector = VTAPIConnector(api_key=API_KEY)
    mock_vt_client.get_object.side_effect = APIError("FailedError", "Failed")
    connector.get_analysis(mock_vt_client, "analysis_id")
    result = connector.results[0]
    assert result.status == "ERROR"
    assert "Failed" in result.error
