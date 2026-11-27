from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import pytest
from sekoia_automation import constants


@pytest.fixture
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield Path(constants.DATA_STORAGE)

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Never really wait in the unit tests: the triggers, tenacity and urllib3 retries all call time.sleep."""
    sleeps: list[float] = []
    monkeypatch.setattr("time.sleep", sleeps.append)
    return sleeps
