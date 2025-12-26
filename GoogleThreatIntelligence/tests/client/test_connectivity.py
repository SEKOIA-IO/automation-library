import vt
from unittest.mock import MagicMock
from googlethreatintelligence.client import VTAPIConnector


def test_test_connectivity_success():
    connector = VTAPIConnector(api_key="key")
    mock_client = MagicMock()

    mock_user = MagicMock()
    mock_user.id = "u123"
    mock_client.get_object.return_value = mock_user

    connector.test_connectivity(mock_client)
    result = connector.results[-1]

    assert result.method == "GET"
    assert result.endpoint == "/api/v3/users/me"
    assert result.status == "SUCCESS"
    assert result.response["user_id"] == "u123"
    mock_client.get_object.assert_called_once_with("/users/me")


def test_test_connectivity_api_error():
    connector = VTAPIConnector(api_key="key")
    mock_client = MagicMock()

    mock_client.get_object.side_effect = vt.APIError("ConnError", "Connection failed")

    connector.test_connectivity(mock_client)
    result = connector.results[-1]

    assert result.status == "ERROR"
    assert "Connection failed" in result.error
    mock_client.get_object.assert_called_once_with("/users/me")
