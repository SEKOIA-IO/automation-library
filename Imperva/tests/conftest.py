from shutil import rmtree
from tempfile import mkdtemp

import pytest
from sekoia_automation import constants

from imperva.fetch_logs import Config


@pytest.fixture
def config() -> Config:
    return Config(
        API_ID="lorem",
        API_KEY="ipsum",
        BASE_URL="https://imperva.test/api",
    )


@pytest.fixture
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage
