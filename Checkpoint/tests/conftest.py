"""Additional programmatic configuration for pytest."""

import asyncio
import random
from typing import Any, List

import pytest
from faker import Faker

from client.token_refresher import CheckpointToken


@pytest.fixture(scope="session")
def faker_locale() -> List[str]:
    """
    Configure Faker to use correct locale.

    Returns:
        List[str]:
    """
    return ["en"]


@pytest.fixture(scope="session")
def faker_seed() -> int:
    """
    Configure Faker to use correct seed.

    Returns:
        int:
    """
    return random.randint(1, 10000)


@pytest.fixture(scope="session")
def session_faker(faker_locale: List[str], faker_seed: int) -> Faker:
    """
    Configure session lvl Faker to use correct seed and locale.

    Args:
        faker_locale: List[str]
        faker_seed: int

    Returns:
        Faker:
    """
    instance = Faker(locale=faker_locale)
    instance.seed_instance(seed=faker_seed)

    return instance


@pytest.fixture
def http_token(session_faker) -> tuple[CheckpointToken, dict[str, Any]]:
    """
    Generate CheckpointToken.

    Args:
        session_faker: Faker

    Returns:
        Tuple[CheckpointToken, dict[str, Any]]:
    """
    data = CheckpointToken(
        token=session_faker.word(),
        csrf=session_faker.word(),
        expires=session_faker.word(),
        expiresIn=session_faker.pyint(min_value=100, max_value=1000),
    )

    result = {
        "success": True,
        "data": {
            "token": data.token,
            "csrf": data.csrf,
            "expires": data.expires,
            "expiresIn": data.expiresIn,
        },
    }

    return data, result


@pytest.fixture(scope="session")
def event_loop():
    """
    Create event loop for pytest.mark.asyncio.

    Yields:
        loop:
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()

    yield loop

    loop.close()
