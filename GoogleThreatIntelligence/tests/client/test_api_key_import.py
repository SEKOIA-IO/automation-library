import os
from unittest.mock import patch
import importlib
import googlethreatintelligence.client as client_module


def test_api_key_warning_when_missing(caplog):
    """Verify that API_KEY == REDACTED triggers a warning log."""

    with patch.dict(os.environ, {"VT_API_KEY": "REDACTED"}, clear=True):
        with caplog.at_level("WARNING"):
            importlib.reload(client_module)

    assert "API_KEY not set! Set VT_API_KEY environment variable" in caplog.text
    assert client_module.API_KEY == "REDACTED"


def test_api_key_loaded_from_env():
    """Verify that API_KEY imports correctly when set."""
    with patch.dict(os.environ, {"VT_API_KEY": "MY_REAL_KEY"}, clear=True):
        importlib.reload(client_module)

    assert client_module.API_KEY == "MY_REAL_KEY"
