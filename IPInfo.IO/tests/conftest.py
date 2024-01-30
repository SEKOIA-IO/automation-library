import uuid
from shutil import rmtree
from tempfile import mkdtemp
from pathlib import Path

import pytest
from sekoia_automation import config
from sekoia_automation import storage as storage_module


@pytest.fixture(autouse=True, scope="session")
def symphony_storage():
    new_storage = Path(mkdtemp())

    yield new_storage
    rmtree(new_storage.as_posix())


@pytest.fixture()
def config_storage():
    old_config_storage = config.VOLUME_PATH
    config.VOLUME_PATH = mkdtemp()
    storage_module.VOLUME_PATH = config.VOLUME_PATH

    yield Path(config.VOLUME_PATH)

    rmtree(config.VOLUME_PATH)
    config.VOLUME_PATH = old_config_storage


@pytest.fixture
def mocked_uuid(mocker):
    mock_uuid = mocker.patch.object(uuid, "uuid4", autospec=True)
    mock_uuid.return_value = uuid.UUID(hex="00000000000000000000000000000000")
    return mock_uuid
