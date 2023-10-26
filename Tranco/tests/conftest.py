from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

from sekoia_automation import config
from sekoia_automation import storage as storage_module
import pytest


@pytest.fixture()
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
