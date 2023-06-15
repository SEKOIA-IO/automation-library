from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import pytest
from sekoia_automation import constants

from sentinelone_module.base import SentinelOneConfiguration, SentinelOneModule


@pytest.fixture
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield Path(constants.DATA_STORAGE)

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture(scope="session")
def sentinelone_hostname():
    return "abcdef.sentinelone.net"


@pytest.fixture(scope="session")
def sentinelone_module(sentinelone_hostname):
    module = SentinelOneModule()
    module.configuration = SentinelOneConfiguration(hostname=sentinelone_hostname, api_token="1234567890")
    return module
