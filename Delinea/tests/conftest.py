"""Additional programmatic configuration for pytest."""

import asyncio
import random
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from typing import List
from unittest.mock import AsyncMock

import pytest
from faker import Faker
from sekoia_automation import constants

from delinea import DelineaModule, DelineaModuleConfiguration


@pytest.fixture
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield Path(constants.DATA_STORAGE)

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


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


@pytest.fixture(scope="session")
def event_loop():
    """
    Create event loop for pytest.mark.asyncio.

    Yields:
        loop:
    """
    loop = asyncio.get_event_loop()

    yield loop

    loop.close()


@pytest.fixture
def base_url(session_faker: Faker) -> str:
    """
    Base URL for Delinea instance.

    Returns:
        str:
    """
    return session_faker.url()


@pytest.fixture
def client_id(session_faker: Faker) -> str:
    """
    Client ID for Delinea instance.

    Returns:
        str:
    """
    return session_faker.word()


@pytest.fixture
def client_secret(faker: Faker) -> str:
    """
    Client Secret for Delinea instance.

    Returns:
        str:
    """
    return faker.word()


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
def delinea_module(base_url, client_id, client_secret) -> DelineaModule:
    """
    Delinea module.

    Args:
        base_url: Base URL for Delinea instance.
        client_id: Client ID for Delinea instance.
        client_secret: Client Secret for Delinea instance.

    Returns:
        DelineaModule:
    """
    module = DelineaModule()
    module.configuration = DelineaModuleConfiguration(
        base_url=base_url, client_id=client_id, client_secret=client_secret
    )

    return module
