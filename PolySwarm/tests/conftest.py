from shutil import rmtree
from tempfile import mkdtemp

import pytest
from sekoia_automation import constants

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.models import PolyswarmModuleConfiguration


@pytest.fixture
def data_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture
def module() -> PolyswarmModule:
    module = PolyswarmModule()
    module.configuration = PolyswarmModuleConfiguration(apikey="test-api-key", community="default")
    return module
