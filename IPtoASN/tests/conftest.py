import uuid
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import pytest


@pytest.fixture()
def symphony_storage():
    new_storage = Path(mkdtemp())

    yield new_storage

    rmtree(new_storage.as_posix())


@pytest.fixture
def mocked_uuid(mocker):
    mock_uuid = mocker.patch.object(uuid, "uuid4", autospec=True)
    mock_uuid.return_value = uuid.UUID(hex="00000000000000000000000000000000")
    return mock_uuid
