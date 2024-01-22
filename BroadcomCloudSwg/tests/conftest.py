"""Additional programmatic configuration for pytest."""

import asyncio
import datetime
import random
from typing import List

import pytest
from faker import Faker

from client.broadcom_cloud_swg_client import BroadcomCloudSwgClient


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
def logs_content(session_faker) -> str:
    """
    Generate logs content.

    Args:
        session_faker: Faker
    """
    number_of_rows = session_faker.random.randint(1, 50)

    # 3 fields in logs
    rows = [
        "\t".join(
            [
                session_faker.past_datetime(datetime.datetime.utcnow()).strftime(BroadcomCloudSwgClient._time_format),
                session_faker.word(),
                session_faker.word(),
            ]
        )
        for _ in range(number_of_rows)
    ]

    headers = "\n".join(
        [
            "#Version:\t1.0",
            "#Date:\t12-Jan-1996 00:00:00",
            "#Fields:\ttime\tcs-method\ts-action",
        ]
    )

    return headers + "\n" + "\n".join(rows)


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
