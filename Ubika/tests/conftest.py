import time
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import MagicMock

import pytest
from sekoia_automation import constants


@pytest.fixture
def data_storage():
    """
    Provide a fresh temporary directory for connector data files.
    """
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture(autouse=True)
def disable_sleep(monkeypatch):
    """
    Prevent any real time.sleep across all tests.
    """
    monkeypatch.setattr(time, "sleep", lambda s: None)


@pytest.fixture
def sleep_spy(monkeypatch):
    """
    Re-patch time.sleep to a MagicMock so tests can inspect call_count.
    """
    spy = MagicMock()
    monkeypatch.setattr(time, "sleep", spy)
    return spy
