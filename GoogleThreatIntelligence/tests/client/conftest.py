import pytest
from unittest.mock import MagicMock
import vt

@pytest.fixture
def mock_vt_client(monkeypatch):
    """Mock vt.Client context manager"""
    mock_client_instance = MagicMock()
    mock_client = MagicMock()
    mock_client.return_value.__enter__.return_value = mock_client_instance
    monkeypatch.setattr(vt, "Client", mock_client)
    return mock_client_instance

@pytest.fixture
def fake_file(tmp_path):
    """Create a temporary fake file"""
    file_path = tmp_path / "testfile.txt"
    file_path.write_text("dummy content")
    return str(file_path)
