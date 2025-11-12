from unittest.mock import patch, MagicMock
import vt
from googlethreatintelligence.get_file_behaviour import GTIGetFileBehaviour

# === Test constants ===
API_KEY = "FAKE_API_KEY"
FILE_HASH = "44d88612fea8a8f36de82e1278abb02f"


@patch('googlethreatintelligence.get_file_behaviour.vt.Client')
def test_get_file_behaviour_success(mock_vt_client):
    """Test successful retrieval of file behaviour via iterator"""
    # Create a mock behaviour object that VT iterator would return
    mock_behaviour = MagicMock()
    mock_behaviour.sandbox_name = "Windows10"
    mock_behaviour.processes_created = ["cmd.exe", "calc.exe"]
    mock_behaviour.files_written = ["C:\\temp\\file1.tmp"]
    mock_behaviour.files_deleted = []
    mock_behaviour.registry_keys_set = ["HKCU\\Software\\Test"]
    mock_behaviour.dns_lookups = ["example.com"]
    mock_behaviour.ip_traffic = ["8.8.8.8"]

    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    # Make iterator return our fake behaviour
    mock_client_instance.iterator.return_value = iter([mock_behaviour])

    # Setup action
    action = GTIGetFileBehaviour()
    action.module.configuration = {"api_key": API_KEY}

    # Run the action
    response = action.run({
        "entity_type": "files",
        "entity": FILE_HASH
    })

    # Verify response
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is True
    assert "data" in response

    # Verify the data contains behaviour information
    assert response["data"]["behaviours_count"] == 1
    assert isinstance(response["data"]["behaviours"], list)
    assert response["data"]["behaviours"][0]["sandbox_name"] == "Windows10"

    # Verify vt.Client was called with the correct API key
    mock_vt_client.assert_called_once_with(API_KEY)

    # Verify iterator was called with the correct endpoint and limit
    mock_client_instance.iterator.assert_called_once_with(
        f"/files/{FILE_HASH}/behaviours",
        limit=5
    )


@patch('googlethreatintelligence.get_file_behaviour.vt.Client')
def test_get_file_behaviour_fail_api_error(mock_vt_client):
    """Test error handling when VT API raises vt.APIError from iterator"""
    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    # Simulate an API error when calling iterator
    mock_client_instance.iterator.side_effect = vt.APIError("SomeAPIError", "Internal Server Error")

    # Setup action
    action = GTIGetFileBehaviour()
    action.module.configuration = {"api_key": API_KEY}

    # Run the action
    response = action.run({
        "entity_type": "files",
        "entity": FILE_HASH
    })

    # Verify error response
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is False
    assert "data" in response or "error" in response

    # Verify vt.Client was called
    mock_vt_client.assert_called_once_with(API_KEY)

    # Ensure iterator was attempted
    mock_client_instance.iterator.assert_called_once_with(
        f"/files/{FILE_HASH}/behaviours",
        limit=5
    )


def test_get_file_behaviour_no_api_key():
    """Test handling of missing API key"""
    action = GTIGetFileBehaviour()

    # No API key configured
    with patch.object(type(action.module), 'configuration', new_callable=MagicMock) as mock_config:
        mock_config.return_value = {}

        response = action.run({
            "entity_type": "files",
            "entity": FILE_HASH
        })

        assert response is not None
        assert isinstance(response, dict)
        assert response.get("success") is False
        assert "API key" in response.get("error", "")
