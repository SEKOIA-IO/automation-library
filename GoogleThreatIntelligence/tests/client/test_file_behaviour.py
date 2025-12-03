import pytest
from unittest.mock import MagicMock
from googlethreatintelligence.client import VTAPIConnector

API_KEY = "FAKE_API_KEY"

def test_get_file_behaviour_success(mock_vt_client):
    connector = VTAPIConnector(api_key=API_KEY)
    mock_behaviour = MagicMock()
    mock_behaviour.sandbox_name = "sandbox1"
    mock_behaviour.processes_created = ["proc1", "proc2"]
    mock_behaviour.files_written = []
    mock_vt_client.iterator.return_value = iter([mock_behaviour])

    connector.get_file_behaviour(mock_vt_client)
    result = connector.results[0]
    assert result.status == "SUCCESS"
    assert result.response["behaviours_count"] == 1
    assert result.response["behaviours"][0]["sandbox_name"] == "sandbox1"

def test_get_file_behaviour_api_error(mock_vt_client):
    from vt import APIError
    connector = VTAPIConnector(api_key=API_KEY)
    mock_vt_client.iterator.side_effect = APIError("FailedError", "Not available")

    connector.get_file_behaviour(mock_vt_client)
    result = connector.results[0]
    assert result.status == "NOT_AVAILABLE"
    assert "Premium" in result.error
