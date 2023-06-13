from shutil import rmtree
from tempfile import mkdtemp

import pytest
from sekoia_automation import constants


@pytest.fixture
def censys_mock(requests_mock):
    requests_mock.get("https://www.censys.io/api/v1/account", json={})
    yield requests_mock


@pytest.fixture(autouse=True, scope="session")
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage
