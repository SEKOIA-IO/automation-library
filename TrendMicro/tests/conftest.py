from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import MagicMock, patch

import pytest
from sekoia_automation import constants


@pytest.fixture
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield Path(constants.DATA_STORAGE)

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture
def prepare_connector_mocks():
    def _prepare(connector):
        connector.push_events_to_intakes = MagicMock()
        connector.log = MagicMock()
        connector.log_exception = MagicMock()
        return connector

    return _prepare


@pytest.fixture
def mocked_vision_one_time():
    with patch("trendmicro_modules.trigger_vision_one_base.time") as mock_time:
        yield mock_time


@pytest.fixture
def mocked_email_worker_runtime():
    with (
        patch(
            "trendmicro_modules.trigger_email_sec.TrendMicroWorker.get_last_timestamp",
            return_value=0,
        ),
        patch("trendmicro_modules.trigger_email_sec.TrendMicroWorker.set_last_timestamp"),
        patch("trendmicro_modules.trigger_email_sec.time") as mock_time,
    ):
        yield mock_time
