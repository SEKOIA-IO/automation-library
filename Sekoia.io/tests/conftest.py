from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import pytest


@pytest.fixture
def symphony_storage():
    new_storage = Path(mkdtemp())

    yield new_storage

    rmtree(new_storage.as_posix())
