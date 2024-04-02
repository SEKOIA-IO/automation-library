"""Additional fixtures for this package."""

import pytest
from faker import Faker

from connectors.s3 import AwsS3QueuedConfiguration


@pytest.fixture
def aws_s3_queued_config(faker: Faker, intake_key: str) -> AwsS3QueuedConfiguration:
    """
    Create a connector configuration.

    Args:
        faker: Faker
        intake_key: str

    Returns:
        AwsS3QueuedConfiguration:
    """
    return AwsS3QueuedConfiguration(
        intake_key=intake_key,
        queue_name=faker.word(),
    )
