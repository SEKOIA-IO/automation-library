"""Configurations and fixtures for the tests in this directory."""

from shutil import rmtree
from tempfile import mkdtemp

import pytest
from faker import Faker
from sekoia_automation import constants

from connectors import CheckpointModule


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


@pytest.fixture
def checkpoint_module(session_faker: Faker) -> CheckpointModule:
    """
    Create a CheckpointModule instance.

    Args:
        session_faker: Faker

    Returns:
        CheckpointModule:
    """
    module = CheckpointModule()
    module.configuration = {
        "client_id": session_faker.word(),
        "secret_key": session_faker.word(),
        "authentication_url": session_faker.word(),
        "base_url": session_faker.url(),
    }

    return module
