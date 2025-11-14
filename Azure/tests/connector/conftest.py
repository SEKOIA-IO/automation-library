from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

from unittest.mock import AsyncMock

import pytest
from sekoia_automation import constants


@pytest.fixture
def mock_push_data_to_intakes() -> AsyncMock:
    """
    Mocked push_data_to_intakes method.

    Returns:
        AsyncMock:
    """

    def side_effect_return_input(events: list[str]) -> list[str]:
        """
        Return input value.

        Uses in side_effect to return input value from mocked function.

        Args:
            events: list[str]

        Returns:
            list[str]:
        """
        return events

    return AsyncMock(side_effect=side_effect_return_input)


@pytest.fixture
def data_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage
