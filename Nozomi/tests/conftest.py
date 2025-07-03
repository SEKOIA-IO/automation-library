from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import AsyncMock

import pytest
from faker import Faker
from sekoia_automation import constants

from nozomi_networks import NozomiConfiguration, NozomiModule


@pytest.fixture(scope="session")
def faker_locale() -> list[str]:
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
def session_faker(faker_locale: list[str], faker_seed: int) -> Faker:
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
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield Path(constants.DATA_STORAGE)

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture
def nozomi_config(session_faker: Faker) -> dict[str, str]:
    """
    Create a configuration for the NozomiModule.

    Args:
        session_faker: Faker instance

    Returns:
        dict[str, str]:
    """
    return {
        "key_name": session_faker.word(),
        "key_token": session_faker.word(),
        "base_url": "https://test.com",
    }


@pytest.fixture
def module(symphony_storage: Path, nozomi_config: dict[str, str]) -> NozomiModule:
    """
    Args:
        symphony_storage: Path
        nozomi_config: dict[str, str]

    Returns:
        AwsModule: The S1 DeepVisibility module.
    """
    module = NozomiModule()
    module.configuration = NozomiConfiguration(**nozomi_config)

    return module


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
