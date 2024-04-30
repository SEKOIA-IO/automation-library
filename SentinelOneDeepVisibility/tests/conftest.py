from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import pytest
from sekoia_automation import constants
from faker import Faker
from connectors import AwsModule, AwsModuleConfiguration

@pytest.fixture
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield Path(constants.DATA_STORAGE)

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture
def aws_configuration(faker: Faker) -> dict[str, str]:
    """
    Create a configuration for the AWS module.

    Args:
        faker: Faker

    Returns:
        dict[str, str]:
    """
    return {
        "aws_access_key": faker.word(),
        "aws_secret_access_key": faker.word(),
        "aws_region_name": "us-west-2",
    }

@pytest.fixture
def aws_module(symphony_storage: Path, aws_configuration) -> AwsModule:
    """
    Create an AWS module.

    Args:
        symphony_storage: Path
        aws_configuration: dict[str, str]

    Returns:
        AwsModule: The AWS module.
    """
    module = AwsModule()
    module.configuration = AwsModuleConfiguration(**aws_configuration)

    return module