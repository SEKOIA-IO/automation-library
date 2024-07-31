from unittest.mock import AsyncMock

import pytest
from faker import Faker

from connectors import TrellixModule


@pytest.fixture(scope="session")
def module(session_faker: Faker) -> TrellixModule:
    """
    Generate TrellixModule.

    Args:
        session_faker: Faker

    Returns:
        TrellixModule:
    """
    module = TrellixModule()

    module.configuration = {
        "client_id": session_faker.word(),
        "client_secret": session_faker.word(),
        "api_key": session_faker.word(),
        "delay": session_faker.random.randint(1, 10),
        "auth_url": session_faker.uri(),
        "base_url": session_faker.uri(),
    }

    return module


@pytest.fixture
def pushed_events_ids(session_faker) -> list[str]:
    """
    Generate random list of events ids.

    Args:
        session_faker: Faker
    Returns:
        list[str]:
    """
    return [session_faker.word() for _ in range(session_faker.random.randint(1, 100))]


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
