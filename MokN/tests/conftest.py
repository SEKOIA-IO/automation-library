import sys
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import pytest
from sekoia_automation import constants

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def data_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()
    Path(constants.DATA_STORAGE, "context.json").write_text("{}", encoding="utf-8")

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage
