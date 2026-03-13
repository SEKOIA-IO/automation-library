from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path
import pytest
from googlethreatintelligence.actions.scan_file import GTIScanFile
import vt

API_KEY = "FAKE_API_KEY"


def _create_file_in_data_storage(data_storage: Path, rel_path: str, content: bytes = b"dummy content") -> Path:
    abs_path = data_storage.joinpath(rel_path)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(content)
    return abs_path


# === SUCCESS CASE ===
@patch("googlethreatintelligence.actions.scan_file.vt.Client")
@patch("googlethreatintelligence.actions.scan_file.VTAPIConnector")
@patch("googlethreatintelligence.actions.scan_file.copy_to_tempfile")
def test_scan_file_success(mock_copy, mock_connector_class, mock_vt_client, data_storage, module):
    """Test successful file scan"""

    rel_path = "samples/dummy.bin"
    _create_file_in_data_storage(data_storage, rel_path)

    # Mock copy_to_tempfile context manager
    tmp_path = "/tmp/fake_tmp_dir/dummy.bin"
    mock_copy.return_value.__enter__ = MagicMock(return_value=tmp_path)
    mock_copy.return_value.__exit__ = MagicMock(return_value=False)

    # Mock VTAPIConnector instance
    mock_connector_instance = MagicMock()
    mock_connector_class.return_value = mock_connector_instance

    # Mock the results list - scan_file() appends to this list
    mock_result = MagicMock()
    mock_result.response = {
        "analysis_stats": {"malicious": 0, "suspicious": 0, "harmless": 50},
        "analysis_results": {"scanner1": "clean", "scanner2": "clean"},
    }
    mock_connector_instance.results = [mock_result]
    mock_connector_instance.scan_file.return_value = None

    # Mock vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    # Initialize action and mock configuration
    action = GTIScanFile(module=module, data_path=data_storage)
    action.module.configuration = {"api_key": API_KEY}

    # Run the action with RELATIVE path (prod behavior)
    response = action.run({"file_path": rel_path})

    assert response is not None
    assert response["success"] is True
    assert "data" in response
    assert response["data"]["analysis_stats"]["malicious"] == 0
    assert "analysis_results" in response["data"]
    assert response["data"]["file_path"] == rel_path  # we default to rel_path

    mock_connector_class.assert_called_once_with(API_KEY, url="", domain="", ip="", file_hash="", cve="")
    mock_connector_instance.scan_file.assert_called_once_with(mock_client_instance, tmp_path)
    mock_vt_client.assert_called_once_with(API_KEY, trust_env=True)


# === MISSING API KEY ===
def test_scan_file_no_api_key(data_storage, module):
    """Test behavior when API key is missing"""
    action = GTIScanFile(module=module, data_path=data_storage)

    # Mock module.configuration PropertyMock
    with patch.object(type(action.module), "configuration", new_callable=PropertyMock) as mock_config:
        mock_config.return_value = {}

        response = action.run({"file_path": "samples/dummy.bin"})

        assert response is not None
        assert response["success"] is False
        assert "API key" in response["error"]


# === FILE NOT FOUND (relative path not present in DATA_STORAGE) ===
def test_scan_file_file_not_found(data_storage, module):
    """Test behavior when the file does not exist in DATA_STORAGE"""
    action = GTIScanFile(module=module, data_path=data_storage)
    action.module.configuration = {"api_key": API_KEY}

    with pytest.raises(FileNotFoundError):
        action.run({"file_path": "samples/does_not_exist.bin"})


# === API ERROR HANDLING ===
@patch("googlethreatintelligence.actions.scan_file.vt.Client")
@patch("googlethreatintelligence.actions.scan_file.VTAPIConnector")
@patch("googlethreatintelligence.actions.scan_file.copy_to_tempfile")
def test_scan_file_api_error(mock_copy, mock_connector_class, mock_vt_client, data_storage, module):
    """Test behavior when the VirusTotal API fails"""
    rel_path = "samples/dummy.bin"
    _create_file_in_data_storage(data_storage, rel_path)

    # Mock copy_to_tempfile
    tmp_path = "/tmp/fake_tmp_dir/dummy.bin"
    mock_copy.return_value.__enter__ = MagicMock(return_value=tmp_path)
    mock_copy.return_value.__exit__ = MagicMock(return_value=False)

    # Mock connector that raises an APIError
    mock_connector_instance = MagicMock()
    mock_connector_instance.scan_file.side_effect = vt.APIError("QuotaExceededError", "API quota exceeded")
    mock_connector_class.return_value = mock_connector_instance

    # Mock vt.Client context
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    action = GTIScanFile(module=module, data_path=data_storage)
    action.module.configuration = {"api_key": API_KEY}

    with pytest.raises(vt.APIError):
        action.run({"file_path": rel_path})

    mock_connector_instance.scan_file.assert_called_once_with(mock_client_instance, tmp_path)
    mock_vt_client.assert_called_once_with(API_KEY, trust_env=True)


# === EDGE CASE: Empty results list ===
@patch("googlethreatintelligence.actions.scan_file.vt.Client")
@patch("googlethreatintelligence.actions.scan_file.VTAPIConnector")
@patch("googlethreatintelligence.actions.scan_file.copy_to_tempfile")
def test_scan_file_empty_results(mock_copy, mock_connector_class, mock_vt_client, data_storage, module):
    """Test behavior when connector.results is empty (edge case)"""
    rel_path = "samples/dummy.bin"
    _create_file_in_data_storage(data_storage, rel_path)

    # Mock copy_to_tempfile
    tmp_path = "/tmp/fake_tmp_dir/dummy.bin"
    mock_copy.return_value.__enter__ = MagicMock(return_value=tmp_path)
    mock_copy.return_value.__exit__ = MagicMock(return_value=False)

    mock_connector_instance = MagicMock()
    mock_connector_instance.results = []  # Empty results list
    mock_connector_instance.scan_file.return_value = None
    mock_connector_class.return_value = mock_connector_instance

    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    action = GTIScanFile(module=module, data_path=data_storage)
    action.module.configuration = {"api_key": API_KEY}

    response = action.run({"file_path": rel_path})

    assert response is not None
    assert response["success"] is False
    assert "error" in response


# === MISSING FILE_PATH ARGUMENT ===
def test_scan_file_missing_file_path_argument(data_storage, module):
    """Test behavior when file_path argument is missing"""
    action = GTIScanFile(module=module, data_path=data_storage)
    action.module.configuration = {"api_key": API_KEY}

    response = action.run({})

    assert response is not None
    assert response["success"] is False
    assert "file_path" in response["error"]


# === ABSOLUTE PATH THAT EXISTS ===
@patch("googlethreatintelligence.actions.scan_file.vt.Client")
@patch("googlethreatintelligence.actions.scan_file.VTAPIConnector")
@patch("googlethreatintelligence.actions.scan_file.copy_to_tempfile")
def test_scan_file_absolute_path_exists(mock_copy, mock_connector_class, mock_vt_client, data_storage, module):
    """Test behavior when an absolute path is provided and the file exists at that absolute path"""

    # Create a file in data_storage
    rel_path = "samples/absolute_test.bin"
    abs_path = _create_file_in_data_storage(data_storage, rel_path)

    # Mock copy_to_tempfile context manager
    tmp_path = "/tmp/fake_tmp_dir/absolute_test.bin"
    mock_copy.return_value.__enter__ = MagicMock(return_value=tmp_path)
    mock_copy.return_value.__exit__ = MagicMock(return_value=False)

    # Mock VTAPIConnector instance
    mock_connector_instance = MagicMock()
    mock_connector_class.return_value = mock_connector_instance

    # Mock the results list
    mock_result = MagicMock()
    mock_result.response = {
        "analysis_stats": {"malicious": 0, "suspicious": 0, "harmless": 50},
        "analysis_results": {"scanner1": "clean"},
    }
    mock_connector_instance.results = [mock_result]
    mock_connector_instance.scan_file.return_value = None

    # Mock vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    # Initialize action and mock configuration
    action = GTIScanFile(module=module, data_path=data_storage)
    action.module.configuration = {"api_key": API_KEY}

    # Run the action with ABSOLUTE path
    response = action.run({"file_path": str(abs_path)})

    assert response is not None
    assert response["success"] is True
    assert "analysis_stats" in response["data"]


# === ABSOLUTE PATH THAT DOESN'T EXIST BUT RELATIVE TO DATA_PATH EXISTS ===
@patch("googlethreatintelligence.actions.scan_file.vt.Client")
@patch("googlethreatintelligence.actions.scan_file.VTAPIConnector")
@patch("googlethreatintelligence.actions.scan_file.copy_to_tempfile")
def test_scan_file_absolute_path_fallback_to_data_path(
    mock_copy, mock_connector_class, mock_vt_client, data_storage, module
):
    """Test behavior when an absolute path doesn't exist but the relative version exists in data_path

    The code uses raw_path.relative_to(raw_path.anchor) which strips only the leading '/'
    So /samples/fallback_test.bin becomes samples/fallback_test.bin
    """

    # Create a file in data_storage
    rel_path = "samples/fallback_test.bin"
    _create_file_in_data_storage(data_storage, rel_path)

    # Use an absolute path that starts with / followed by the relative path
    # When path.relative_to(path.anchor) is called, it strips the leading /
    fake_absolute_path = f"/{rel_path}"

    # Mock copy_to_tempfile context manager
    tmp_path = "/tmp/fake_tmp_dir/fallback_test.bin"
    mock_copy.return_value.__enter__ = MagicMock(return_value=tmp_path)
    mock_copy.return_value.__exit__ = MagicMock(return_value=False)

    # Mock VTAPIConnector instance
    mock_connector_instance = MagicMock()
    mock_connector_class.return_value = mock_connector_instance

    # Mock the results list
    mock_result = MagicMock()
    mock_result.response = {
        "analysis_stats": {"malicious": 0, "suspicious": 0, "harmless": 50},
        "analysis_results": {"scanner1": "clean"},
    }
    mock_connector_instance.results = [mock_result]
    mock_connector_instance.scan_file.return_value = None

    # Mock vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    # Initialize action and mock configuration
    action = GTIScanFile(module=module, data_path=data_storage)
    action.module.configuration = {"api_key": API_KEY}

    # Run the action with fake absolute path
    response = action.run({"file_path": fake_absolute_path})

    assert response is not None
    assert response["success"] is True
    assert "analysis_stats" in response["data"]


# === FILE PATH IS A DIRECTORY ===
def test_scan_file_path_is_directory(data_storage, module):
    """Test behavior when the file_path points to a directory instead of a file"""
    # Create a directory
    dir_path = data_storage.joinpath("samples/test_dir")
    dir_path.mkdir(parents=True, exist_ok=True)

    action = GTIScanFile(module=module, data_path=data_storage)
    action.module.configuration = {"api_key": API_KEY}

    with pytest.raises(FileNotFoundError):
        action.run({"file_path": "samples/test_dir"})


# === RESPONSE IS NONE WITH ERROR ===
@patch("googlethreatintelligence.actions.scan_file.vt.Client")
@patch("googlethreatintelligence.actions.scan_file.VTAPIConnector")
@patch("googlethreatintelligence.actions.scan_file.copy_to_tempfile")
def test_scan_file_response_none_with_error(mock_copy, mock_connector_class, mock_vt_client, data_storage, module):
    """Test behavior when response is None but error is set"""
    rel_path = "samples/dummy.bin"
    _create_file_in_data_storage(data_storage, rel_path)

    # Mock copy_to_tempfile
    tmp_path = "/tmp/fake_tmp_dir/dummy.bin"
    mock_copy.return_value.__enter__ = MagicMock(return_value=tmp_path)
    mock_copy.return_value.__exit__ = MagicMock(return_value=False)

    mock_connector_instance = MagicMock()
    mock_result = MagicMock()
    mock_result.response = None
    mock_result.error = "Specific error from connector"
    mock_connector_instance.results = [mock_result]
    mock_connector_instance.scan_file.return_value = None
    mock_connector_class.return_value = mock_connector_instance

    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    action = GTIScanFile(module=module, data_path=data_storage)
    action.module.configuration = {"api_key": API_KEY}

    response = action.run({"file_path": rel_path})

    assert response is not None
    assert response["success"] is False
    assert response["error"] == "Specific error from connector"


# === RESPONSE IS NONE WITHOUT ERROR ===
@patch("googlethreatintelligence.actions.scan_file.vt.Client")
@patch("googlethreatintelligence.actions.scan_file.VTAPIConnector")
@patch("googlethreatintelligence.actions.scan_file.copy_to_tempfile")
def test_scan_file_response_none_without_error(mock_copy, mock_connector_class, mock_vt_client, data_storage, module):
    """Test behavior when response is None and error is also None"""
    rel_path = "samples/dummy.bin"
    _create_file_in_data_storage(data_storage, rel_path)

    # Mock copy_to_tempfile
    tmp_path = "/tmp/fake_tmp_dir/dummy.bin"
    mock_copy.return_value.__enter__ = MagicMock(return_value=tmp_path)
    mock_copy.return_value.__exit__ = MagicMock(return_value=False)

    mock_connector_instance = MagicMock()
    mock_result = MagicMock()
    mock_result.response = None
    mock_result.error = None
    mock_connector_instance.results = [mock_result]
    mock_connector_instance.scan_file.return_value = None
    mock_connector_class.return_value = mock_connector_instance

    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    action = GTIScanFile(module=module, data_path=data_storage)
    action.module.configuration = {"api_key": API_KEY}

    response = action.run({"file_path": rel_path})

    assert response is not None
    assert response["success"] is False
    assert "Scan failed with empty response" in response["error"]


# === MULTIPLE RESULTS - USES LAST ONE ===
@patch("googlethreatintelligence.actions.scan_file.vt.Client")
@patch("googlethreatintelligence.actions.scan_file.VTAPIConnector")
@patch("googlethreatintelligence.actions.scan_file.copy_to_tempfile")
def test_scan_file_uses_last_result(mock_copy, mock_connector_class, mock_vt_client, data_storage, module):
    """Test that the action uses the last result when multiple results are present"""
    rel_path = "samples/dummy.bin"
    _create_file_in_data_storage(data_storage, rel_path)

    # Mock copy_to_tempfile
    tmp_path = "/tmp/fake_tmp_dir/dummy.bin"
    mock_copy.return_value.__enter__ = MagicMock(return_value=tmp_path)
    mock_copy.return_value.__exit__ = MagicMock(return_value=False)

    mock_connector_instance = MagicMock()

    # First result
    mock_result1 = MagicMock()
    mock_result1.response = {
        "analysis_stats": {"malicious": 10},
        "analysis_results": {"scanner1": "malicious"},
    }

    # Second/last result (should be used)
    mock_result2 = MagicMock()
    mock_result2.response = {
        "analysis_stats": {"malicious": 0},
        "analysis_results": {"scanner1": "clean"},
    }

    mock_connector_instance.results = [mock_result1, mock_result2]
    mock_connector_instance.scan_file.return_value = None
    mock_connector_class.return_value = mock_connector_instance

    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    action = GTIScanFile(module=module, data_path=data_storage)
    action.module.configuration = {"api_key": API_KEY}

    response = action.run({"file_path": rel_path})

    assert response is not None
    assert response["success"] is True
    # Should use the LAST result (malicious: 0, not 10)
    assert response["data"]["analysis_stats"]["malicious"] == 0


# === FILE_PATH FROM ANALYSIS RESPONSE ===
@patch("googlethreatintelligence.actions.scan_file.vt.Client")
@patch("googlethreatintelligence.actions.scan_file.VTAPIConnector")
@patch("googlethreatintelligence.actions.scan_file.copy_to_tempfile")
def test_scan_file_uses_file_path_from_response(mock_copy, mock_connector_class, mock_vt_client, data_storage, module):
    """Test that file_path from analysis response is used if present"""
    rel_path = "samples/dummy.bin"
    _create_file_in_data_storage(data_storage, rel_path)

    # Mock copy_to_tempfile
    tmp_path = "/tmp/fake_tmp_dir/dummy.bin"
    mock_copy.return_value.__enter__ = MagicMock(return_value=tmp_path)
    mock_copy.return_value.__exit__ = MagicMock(return_value=False)

    mock_connector_instance = MagicMock()
    mock_result = MagicMock()
    mock_result.response = {
        "analysis_stats": {"malicious": 0},
        "analysis_results": {},
        "file_path": "/original/path/from/response.bin",
    }
    mock_connector_instance.results = [mock_result]
    mock_connector_instance.scan_file.return_value = None
    mock_connector_class.return_value = mock_connector_instance

    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    action = GTIScanFile(module=module, data_path=data_storage)
    action.module.configuration = {"api_key": API_KEY}

    response = action.run({"file_path": rel_path})

    assert response is not None
    assert response["success"] is True
    # Should use file_path from response, not rel_path
    assert response["data"]["file_path"] == "/original/path/from/response.bin"
