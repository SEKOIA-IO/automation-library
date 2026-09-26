from unittest.mock import patch, MagicMock
import vt
from googlethreatintelligence.actions.get_file_behaviour import GTIGetFileBehaviour

# === Test constants ===
API_KEY = "FAKE_API_KEY"
FILE_HASH = "44d88612fea8a8f36de82e1278abb02f"


@patch("googlethreatintelligence.actions.get_file_behaviour.vt.Client")
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
    mock_behaviour.to_dict = MagicMock(
        return_value={
            "attributes": {
                "sandbox_name": "Windows10",
                "processes_created": ["cmd.exe", "calc.exe"],
                "files_written": ["C:\\temp\\file1.tmp"],
                "files_deleted": [],
                "registry_keys_set": ["HKCU\\Software\\Test"],
                "dns_lookups": ["example.com"],
                "ip_traffic": ["8.8.8.8"],
            }
        }
    )

    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    # Make iterator return our fake behaviour
    mock_client_instance.iterator.return_value = iter([mock_behaviour])

    # Setup action
    action = GTIGetFileBehaviour()
    action.module.configuration = {"api_key": API_KEY}

    # Run the action with correct argument name
    response = action.run({"file_hash": FILE_HASH})

    # Verify response
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is True

    # Verify the response contains behaviour information (fields at root level)
    assert response["behaviours_count"] == 1
    assert isinstance(response["behaviours"], list)
    assert response["behaviours"][0]["sandbox_name"] == "Windows10"
    # Verify flattened/merged fields at root level
    assert response["sandbox_names"] == ["Windows10"]
    assert response["file_hash"] is not None

    # Verify vt.Client was called with the correct API key
    mock_vt_client.assert_called_once_with(API_KEY, trust_env=True)

    # Verify iterator was called with the correct endpoint and limit
    mock_client_instance.iterator.assert_called_once_with(f"/files/{FILE_HASH}/behaviours")


@patch("googlethreatintelligence.actions.get_file_behaviour.vt.Client")
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

    # Run the action with correct argument name
    response = action.run({"file_hash": FILE_HASH})

    # Verify error response - connector handles API error gracefully
    # and returns a response with empty fields and success=False
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is False
    # When API error occurs, connector returns empty lists for all fields
    assert response.get("behaviours") == []
    assert response.get("behaviours_count") == 0

    # Verify vt.Client was called
    mock_vt_client.assert_called_once_with(API_KEY, trust_env=True)

    # Ensure iterator was attempted
    mock_client_instance.iterator.assert_called_once_with(f"/files/{FILE_HASH}/behaviours")


def test_get_file_behaviour_no_api_key():
    """Test handling of missing API key"""
    from unittest.mock import PropertyMock

    action = GTIGetFileBehaviour()

    with patch.object(type(action.module), "configuration", new_callable=PropertyMock) as mock_config:
        mock_config.return_value = {}
        response = action.run({"file_hash": FILE_HASH})

    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is False
    assert "API key" in response.get("error", "")


@patch("googlethreatintelligence.actions.get_file_behaviour.vt.Client")
def test_get_file_behaviour_generic_exception(mock_vt_client):
    """Test generic exception handler."""
    mock_vt_client.side_effect = RuntimeError("unexpected failure")

    action = GTIGetFileBehaviour()
    action.module.configuration = {"api_key": API_KEY}

    response = action.run({"file_hash": FILE_HASH})

    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is False
    assert "unexpected failure" in response.get("error", "")
