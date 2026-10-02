"""Test fixtures for asset connector tests."""

from pathlib import Path

import pytest


@pytest.fixture
def data_storage(tmp_path: Path) -> Path:
    """Create a temporary data storage directory for tests.

    Args:
        tmp_path: Pytest temporary path fixture.

    Returns:
        Path to temporary data storage directory.
    """
    storage = tmp_path / "data_storage"
    storage.mkdir()
    return storage
