from unittest.mock import patch, MagicMock, PropertyMock
from googlethreatintelligence.scan_file import GTIScanFile
import vt
import tempfile
import os

API_KEY = "FAKE_API_KEY"

# === SUCCESS CASE ===
@patch("googlethreatintelligence.scan_file.vt.Client")
@patch("googlethreatintelligence.scan_file.VTAPIConnector")
def test_scan_file_success(mock_connector_class, mock_vt_client):
    """Test successful file scan"""

    # Create a temporary file to simulate a real file
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(b"dummy content")

    try:
        # Mock VTAPIConnector instance
        mock_connector_instance = MagicMock()
        mock_connector_class.return_value = mock_connector_instance
        mock_connector_instance.scan_file.return_value = "analysis_1234"

        # Mock vt.Client context manager
        mock_client_instance = MagicMock()
        mock_vt_client.return_value.__enter__.return_value = mock_client_instance

        # Initialize action and mock configuration
        action = GTIScanFile()
        action.module.configuration = {"api_key": API_KEY}

        # Run the action
        response = action.run({"file_path": tmp_path})

        # === Assertions ===
        assert response is not None
        assert response["success"] is True
        assert response["analysis_id"] == "analysis_1234"
        assert response["file_path"] == tmp_path

        mock_connector_class.assert_called_once_with(API_KEY)
        mock_connector_instance.scan_file.assert_called_once_with(mock_client_instance, tmp_path)
        mock_vt_client.assert_called_once_with(API_KEY)
    finally:
        os.unlink(tmp_path)


# === MISSING API KEY ===
def test_scan_file_no_api_key():
    """Test behavior when API key is missing"""
    action = GTIScanFile()

    # Correctly mock the module.configuration PropertyMock
    with patch.object(type(action.module), "configuration", new_callable=PropertyMock) as mock_config:
        mock_config.return_value = {}

        response = action.run({"file_path": "dummy_path"})

        assert response is not None
        assert response["success"] is False
        assert "API key" in response["error"]


# === FILE NOT FOUND ===
def test_scan_file_file_not_found():
    """Test behavior when the file does not exist"""
    action = GTIScanFile()
    action.module.configuration = {"api_key": API_KEY}

    response = action.run({"file_path": "/nonexistent/file.txt"})

    assert response is not None
    assert response["success"] is False
    assert "File not found" in response["error"]


# === API ERROR HANDLING ===
@patch("googlethreatintelligence.scan_file.vt.Client")
@patch("googlethreatintelligence.scan_file.VTAPIConnector")
def test_scan_file_api_error(mock_connector_class, mock_vt_client):
    """Test behavior when the VirusTotal API fails"""
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(b"dummy content")

    try:
        # Mock connector that raises an APIError
        mock_connector_instance = MagicMock()
        mock_connector_instance.scan_file.side_effect = vt.APIError("QuotaExceededError", "API quota exceeded")
        mock_connector_class.return_value = mock_connector_instance

        # Mock vt.Client context
        mock_client_instance = MagicMock()
        mock_vt_client.return_value.__enter__.return_value = mock_client_instance

        action = GTIScanFile()
        action.module.configuration = {"api_key": API_KEY}

        response = action.run({"file_path": tmp_path})

        assert response is not None
        assert response["success"] is False
        assert "API quota exceeded" in response["error"]

        mock_connector_instance.scan_file.assert_called_once()
        mock_vt_client.assert_called_once_with(API_KEY)
    finally:
        os.unlink(tmp_path)
