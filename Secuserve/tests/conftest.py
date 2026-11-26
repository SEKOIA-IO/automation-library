from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import MagicMock

import pytest
from sekoia_automation import constants

from secuserve_modules import SecuserveModule
from secuserve_modules.connector_esecuremail_events import (
    ESecuremailEventsConfiguration,
    ESecuremailEventsConnector,
)
from secuserve_modules.models import SecuserveModuleConfiguration

API_HOST = "https://console.example.net"
API_URL = f"{API_HOST}/siem/suivi"


@pytest.fixture
def data_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield Path(constants.DATA_STORAGE)

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture
def module():
    module = SecuserveModule()
    module.configuration = SecuserveModuleConfiguration(api_host=API_HOST)
    return module


@pytest.fixture
def connector(module, data_storage):
    connector = ESecuremailEventsConnector(module=module, data_path=data_storage)
    connector.configuration = ESecuremailEventsConfiguration(
        api_key="an-api-key",
        intake_key="an-intake-key",
        frequency=60,
        chunk_size=2,
    )
    connector.log = MagicMock()
    connector.log_exception = MagicMock()
    connector.push_events_to_intakes = MagicMock()
    return connector


def set_cursor(connector, moment):
    """
    Move the checkpoint to an arbitrary date.

    `CheckpointDatetime.offset` only ever moves forward, so a test that needs to
    start from the past has to seed the context itself.
    """
    with connector.cursor._context as cache:
        cache["most_recent_date_seen"] = moment.isoformat()
    connector.cursor._most_recent_date_seen = None
