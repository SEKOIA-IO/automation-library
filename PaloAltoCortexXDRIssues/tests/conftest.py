from shutil import rmtree
from tempfile import mkdtemp

import pytest
from sekoia_automation import constants

from cortex_module.base import CortexModule


@pytest.fixture
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.SYMPHONY_STORAGE = original_storage


@pytest.fixture
def module() -> CortexModule:
    cortex_module = CortexModule()
    cortex_module.configuration = {
        "api_key": "72b9f5b1-5e9f-47aa-9912-2503bfc319e6",
        "api_key_id": "99",
        "fqdn": "XXXX.test.paloaltonetworks.com",
    }

    return cortex_module
