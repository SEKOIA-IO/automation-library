"""Additional programmatic configuration for pytest."""

import asyncio
import random
from typing import List
from unittest.mock import patch

import pytest
from faker import Faker

from client.http_client import SalesforceHttpClient
from client.schemas.token import HttpToken
from client.token_refresher import SalesforceTokenRefresher


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
def token_refresher_session():
    """
    Mock session for SalesforceTokenRefresher.

    Yields:
        MagicMock:
    """
    with patch.object(SalesforceTokenRefresher, "_session") as session_mock:
        yield session_mock


@pytest.fixture
def http_client_session():
    """
    Mock session for SalesforceHttpClient.

    Yields:
        MagicMock:
    """
    with patch.object(SalesforceHttpClient, "_session") as session_mock:
        yield session_mock


@pytest.fixture
def http_token(session_faker) -> HttpToken:
    """
    Generate HttpToken.

    Args:
        session_faker: Faker

    Returns:
        HttpToken:
    """
    return HttpToken(
        access_token=session_faker.word(),
        signature=session_faker.word(),
        instance_url=session_faker.word(),
        id=session_faker.word(),
        token_type=session_faker.word(),
        issued_at=session_faker.word(),
    )


@pytest.fixture
def csv_content(session_faker) -> str:
    """
    Generate csv content.

    Args:
        session_faker: Faker
    """
    number_of_columns = session_faker.random.randint(1, 10)
    number_of_rows = session_faker.random.randint(1, 50)

    columns = [session_faker.word().upper() for _ in range(number_of_columns)]
    rows = [",".join([session_faker.word() for _ in range(number_of_columns)]) for _ in range(number_of_rows)]

    return "\n".join([",".join(columns)] + rows)


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
