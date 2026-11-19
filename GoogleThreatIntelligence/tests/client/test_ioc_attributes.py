import vt
from unittest.mock import MagicMock
from googlethreatintelligence.client import VTAPIConnector


def test_ioc_report_with_specific_attributes():
    connector = VTAPIConnector(api_key="k")
    mock_client = MagicMock()

    mock_obj = MagicMock()
    mock_obj.id = "hash123"
    mock_obj.reputation = 10
    mock_obj.last_analysis_stats = {"malicious": 1, "undetected": 50}
    mock_obj.country = "FR"
    mock_obj.categories = {"malware": True}

    mock_client.get_object.return_value = mock_obj

    connector.get_ioc_report(mock_client, "files", "hash123")
    result = connector.results[-1]

    assert result.status == "SUCCESS"
    assert result.response["last_analysis_stats"] == {"malicious": 1, "undetected": 50}
    assert result.response["country"] == "FR"
    assert result.response["categories"] == {"malware": True}
