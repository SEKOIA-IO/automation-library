import sys
import time
from collections.abc import Iterator
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import pytest
import respx
from sekoia_automation import constants

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tests.payloads import BASE  # noqa: E402
from urlscan_modules import UrlScanModule  # noqa: E402
from urlscan_modules.models import UrlScanModuleConfiguration  # noqa: E402


@pytest.fixture
def data_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture
def module() -> UrlScanModule:
    module = UrlScanModule()
    module.configuration = UrlScanModuleConfiguration(api_key="test-api-key")
    return module


@pytest.fixture(autouse=True)
def clock(monkeypatch) -> list[float]:
    """Fake time: time.sleep(s) advances time.time() by s, nothing really waits."""
    now = [1_800_000_000.0]
    monkeypatch.setattr(time, "time", lambda: now[0])
    monkeypatch.setattr(time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    return now


@pytest.fixture
def api() -> Iterator[respx.MockRouter]:
    """urlscan.io mock: unmocked requests fail, unused routes are allowed."""
    with respx.mock(base_url=BASE, assert_all_called=False) as router:
        yield router
