from pathlib import Path
from queue import Queue
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import Mock

import pytest
from sekoia_automation import constants

from retarus_modules.connector import RetarusConnector


@pytest.fixture
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield Path(constants.DATA_STORAGE)

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture
def connector(symphony_storage):
    connector = RetarusConnector(data_path=symphony_storage)
    connector.module.configuration = {}
    connector.configuration = {
        "intake_key": "baz",
        "ws_url": "wss://web.socket",
        "ws_key": "secret",
    }
    connector.log = Mock()
    connector.log_exception = Mock()
    connector.push_events_to_intakes = Mock()
    yield connector


@pytest.fixture
def queue():
    return Queue()
