from shutil import rmtree
from tempfile import mkdtemp

import pytest
from sekoia_automation import constants

from hornetsecurity_modules import HornetsecurityModule
from hornetsecurity_modules.models import HornetsecurityModuleConfiguration


@pytest.fixture
def data_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture
def module():
    """
    Fixture to create an instance of HornetsecurityModule for testing.
    """
    module = HornetsecurityModule()
    module.configuration = HornetsecurityModuleConfiguration(
        api_token="my_api_token",
        api_url="https://cp.hornetsecurity.com/api/v0",
    )
    return module
