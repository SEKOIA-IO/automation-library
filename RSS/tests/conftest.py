import os
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def purge_settings_lru_cache():
    """Reset Settings’s `lru_cache` before every test to prevent wrong
    usage of cache.

    """

    from rss.settings import get_settings

    get_settings.cache_clear()

    yield


@pytest.fixture(autouse=True)
def settings(tmp_path):
    from rss.settings import Settings

    with patch.dict(os.environ, {"SYMPHONY_RSS_CACHE_DIR": str(tmp_path)}):
        yield Settings()
