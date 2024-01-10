"""Additional programmatic configuration for pytest."""

import asyncio
from shutil import rmtree
from tempfile import mkdtemp
from typing import List
from unittest.mock import patch

import pytest
from faker import Faker
from sekoia_automation import constants

from actions import MicrosoftModule, MicrosoftModuleConfiguration


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
    return 123456


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
def symphony_storage() -> str:
    """
    Fixture for symphony temporary storage.

    Yields:
        str:
    """
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.SYMPHONY_STORAGE = original_storage


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


@pytest.fixture
def mock_session():
    """
    Mock the Session object from winrm.

    Yields:
        MagicMock:
    """
    with patch("client.windows_client.Session") as mock_session:
        yield mock_session


@pytest.fixture
def module(session_faker: Faker) -> MicrosoftModule:
    """
    Create a MicrosoftModule with a random configuration.

    Args:
        session_faker: Faker

    Returns:
        MicrosoftModule:
    """
    module = MicrosoftModule()
    config = MicrosoftModuleConfiguration(
        username=session_faker.word(),
        password=session_faker.word(),
    )
    module.configuration = config

    return module
