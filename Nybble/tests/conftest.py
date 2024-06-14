from shutil import rmtree
from tempfile import mkdtemp

import pytest

from sekoia_automation import constants
from nybble_modules import NybbleModule, NybbleConfiguration


@pytest.fixture
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.SYMPHONY_STORAGE = original_storage


@pytest.fixture(scope="session")
def nybble_module():
    module = NybbleModule()
    module.configuration = NybbleConfiguration(
        nhub_url="https://abcdef.nybble-analytics.io", nhub_username="testuser", nhub_key="dummykey"
    )
    return module
