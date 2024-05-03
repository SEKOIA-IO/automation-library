from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import pytest
from sekoia_automation import constants
from faker import Faker
from deep_visibility import SentinelOneDeepVisibilityConfiguration, SentinelOneDeepVisibilityModule


@pytest.fixture
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield Path(constants.DATA_STORAGE)

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture
def deepvisibility_configuration(faker: Faker) -> dict[str, str]:
    """
    Create a configuration for the SentinelOne DeepVisibility module.

    Args:
        faker: Faker

    Returns:
        dict[str, str]:
    """
    return {
        "aws_access_key": faker.word(),
        "aws_secret_access_key": faker.word(),
        "aws_region_name": "us-west-2",
        "intake_key": faker.word(),
        "queue_name": faker.word(),
    }


@pytest.fixture
def deepvisibility_module(symphony_storage: Path, deepvisibility_configuration) -> SentinelOneDeepVisibilityModule:
    """
    Create an SentinelOne DeepVisibility module.

    Args:
        symphony_storage: Path
        aws_configuration: dict[str, str]

    Returns:
        AwsModule: The S1 DeepVisibility module.
    """
    module = SentinelOneDeepVisibilityModule()
    module.configuration = SentinelOneDeepVisibilityConfiguration(**deepvisibility_configuration)

    return module
