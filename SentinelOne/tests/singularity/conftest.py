from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from sentinelone_module.base import SentinelOneConfiguration, SentinelOneModule


@pytest.fixture
def mock_push_data_to_intakes() -> AsyncMock:
    """
    Mocked push_data_to_intakes method.

    Will return the input value.

    Returns:
        AsyncMock:
    """

    def side_effect_return_input(events: list[str]) -> list[str]:
        return events

    return AsyncMock(side_effect=side_effect_return_input)


@pytest.fixture
def sentinel_module(symphony_storage: Path) -> SentinelOneModule:
    """
    Create a SentinelOne module.

    Args:
        symphony_storage: Path
    """
    module = SentinelOneModule()
    module.configuration = SentinelOneConfiguration(
        api_token="test_token",
        hostname="http://testhost",
    )

    return module
