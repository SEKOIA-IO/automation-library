"""Tests related to AwsS3LogsTrigger."""

from pathlib import Path

import pytest
from faker import Faker

from connectors import AwsModule
from deep_visibility.connector_s3_logs import DeepVisibilityConnector
from connectors.s3 import AwsS3QueuedConfiguration


@pytest.fixture
def test_data() -> bytes:
    return """

{"message":"EPP Device Collected","dataSource.vendor":"SentinelOne","timestamp":"2024-04-30T09:06:28.629Z"}
{"src.process.parent.isStorylineRoot":false,"event.category":"indicators","indicator.category":"InfoStealer","event.type":"Behavioral Indicators"}
{"src.process.parent.isStorylineRoot":false,"event.category":"group","src.process.parent.image.sha1":"973efc4a04e2d26ae8777fa86fb7ac19fcd8c4e4"}
{"src.process.parent.isStorylineRoot":false,"event.category":"file","indicator.category":"InfoStealer","event.type":"File Scan"}
2 111111111111 eni-0a479835a7588c9ca 188.114.116.1 172.31.39.167 123 44789 17 1 76 1645469669 1645469724 ACCEPT OK

""".encode(
        "utf-8"
    )


@pytest.fixture
def deepvisibility_s3_logs_trigger_config(faker: Faker) -> AwsS3QueuedConfiguration:
    """
    Create a configuration.

    Args:
        faker: Faker

    Returns:
        DeepVisibilityConfiguration:
    """
    config = {
        "frequency": 0,
        "queue_name": faker.word(),
        "intake_key": faker.word(),
    }

    return AwsS3QueuedConfiguration(**config)


@pytest.fixture
def connector(
    aws_module: AwsModule,
    symphony_storage: Path,
    deepvisibility_s3_logs_trigger_config: AwsS3QueuedConfiguration,
) -> DeepVisibilityConnector:
    """
    Create a connector.

    Args:
        aws_module: AwsModule
        symphony_storage: Path
        deepvisibility_s3_logs_trigger_config: DeepVisibilityConfiguration

    Returns:
        DeepVisibilityConnector:
    """
    connector = DeepVisibilityConnector(module=aws_module, data_path=symphony_storage)

    connector.module = aws_module
    connector.configuration = deepvisibility_s3_logs_trigger_config

    return connector


def test_aws_s3_logs_trigger_parse_data(connector: DeepVisibilityConnector, test_data: bytes):
    """
    Test DeepVisibilityConnector `_parse_data`.

    Args:
        connector: DeepVisibilityConnector
        test_data: bytes
    """

    assert connector._parse_content(test_data) == [
        [line for line in test_data.decode("utf-8").split("\n") if line != ""][1]
    ]
    assert connector._parse_content(b"") == []
