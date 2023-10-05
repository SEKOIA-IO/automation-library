"""Tests related to AwsS3RecordsTrigger."""
import orjson
import pytest
from faker import Faker

from connectors import AwsModule
from connectors.s3 import AwsS3QueuedConfiguration
from connectors.s3.trigger_s3_records import AwsS3RecordsTrigger


@pytest.fixture
def connector(
    aws_module: AwsModule,
    aws_s3_queued_config: AwsS3QueuedConfiguration,
) -> AwsS3RecordsTrigger:
    """
    Create a connector.

    Args:
        aws_module: AwsModule
        aws_s3_queued_config: AwsS3QueuedConfiguration

    Returns:
        AwsS3RecordsTrigger:
    """
    connector = AwsS3RecordsTrigger()

    connector.module = aws_module
    connector.configuration = aws_s3_queued_config

    return connector


def test_aws_s3_records_trigger_parse_content(faker: Faker, connector: AwsS3RecordsTrigger):
    """
    Test AwsS3RecordsTrigger `_parse_content`.

    Args:
        faker: Faker
        connector: AwsS3RecordsTrigger
    """
    data_1 = {"Records": []}

    data_2 = {
        "Records": [
            faker.word(),
            faker.word(),
            faker.word(),
        ]
    }

    data_3 = {
        "Records": [
            "",
            "",
            faker.word(),
            faker.word(),
            faker.word(),
            "",
        ]
    }

    assert connector._parse_content(orjson.dumps(data_1)) == data_1.get("Records")
    assert connector._parse_content(orjson.dumps(data_2)) == data_2.get("Records")
    assert connector._parse_content(orjson.dumps(data_3)) == [
        record for record in data_3.get("Records") if record != ""
    ]
    assert connector._parse_content(b"") == []
