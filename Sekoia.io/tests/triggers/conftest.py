from shutil import rmtree
from tempfile import mkdtemp

import pytest
from sekoia_automation import constants

from .samples import sample_notifications, sample_sicalertapi  # noqa


@pytest.fixture
def module_configuration():
    yield {"base_url": "http://fake.url/", "api_key": "fake_api_key"}


@pytest.fixture
def data_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage
