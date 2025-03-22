"""Tests related to AwsS3RecordsTrigger."""

from pathlib import Path

import orjson
import pytest
from faker import Faker

from connectors import AwsModule
from connectors.s3 import AwsS3QueuedConfiguration
from connectors.s3.trigger_s3_records import AwsS3RecordsTrigger
from tests.helpers import async_list, async_temporary_file


@pytest.fixture
def connector(
    aws_module: AwsModule,
    symphony_storage: Path,
    aws_s3_queued_config: AwsS3QueuedConfiguration,
) -> AwsS3RecordsTrigger:
    """
    Create a connector.

    Args:
        aws_module: AwsModule
        symphony_storage: Path
        aws_s3_queued_config: AwsS3QueuedConfiguration

    Returns:
        AwsS3RecordsTrigger:
    """
    connector = AwsS3RecordsTrigger(module=aws_module, data_path=symphony_storage)

    connector.configuration = aws_s3_queued_config

    return connector


@pytest.mark.asyncio
async def test_aws_s3_records_trigger_parse_content(faker: Faker, connector: AwsS3RecordsTrigger):
    """
    Test AwsS3RecordsTrigger `_parse_content`.

    Args:
        faker: Faker
        connector: AwsS3RecordsTrigger
    """
    data_1 = {"Records": []}

    data_2 = {
        "Records": [
            {"eventSource": faker.word(), "eventName": faker.word()},
            {"eventSource": faker.word(), "eventName": faker.word()},
            {"eventSource": faker.word(), "eventName": faker.word()},
        ]
    }

    data_3 = {
        "Records": [
            {},
            {},
            {"eventSource": faker.word(), "eventName": faker.word()},
            {"eventSource": faker.word(), "eventName": faker.word()},
            {"eventSource": faker.word(), "eventName": faker.word()},
            {},
        ]
    }

    async with async_temporary_file(orjson.dumps(data_1)) as f:
        assert await async_list(connector._parse_content(f)) == [
            orjson.dumps(record).decode("utf-8") for record in data_1.get("Records")
        ]

    async with async_temporary_file(orjson.dumps(data_2)) as f:
        assert await async_list(connector._parse_content(f)) == [
            orjson.dumps(record).decode("utf-8") for record in data_2.get("Records")
        ]

    async with async_temporary_file(orjson.dumps(data_3)) as f:
        assert await async_list(connector._parse_content(f)) == [
            orjson.dumps(record).decode("utf-8") for record in data_3.get("Records") if record != {}
        ]

    async with async_temporary_file(b"") as f:
        assert await async_list(connector._parse_content(f)) == []


def test_check_if_payload_is_valid_1(connector: AwsS3RecordsTrigger, session_faker: Faker):
    """
    Test AwsS3RecordsTrigger `is_valid_payload`.

    Args:
        connector: AwsS3RecordsTrigger
        session_faker: Faker
    """
    assert connector.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "List"}) is False
    assert connector.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "Describe"}) is False
    assert connector.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "GetObjectTagging"}) is False
    assert connector.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "Random"}) is False
    assert connector.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "Delete"}) is True
    assert connector.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "Create"}) is True
    assert connector.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "Copy"}) is True
    assert connector.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "Put"}) is True
    assert connector.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "Restore"}) is True
    assert connector.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "GetObject"}) is False
    assert connector.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "GetObjectTorrent"}) is True
    assert connector.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "ListBuckets"}) is True

    assert connector.is_valid_payload({"eventSource": "random.amazonaws.com", "eventName": "List"}) is False
    assert connector.is_valid_payload({"eventSource": "random.amazonaws.com", "eventName": "Describe"}) is False
    assert connector.is_valid_payload({"eventSource": "random.amazonaws.com", "eventName": "Delete"}) is True
    assert connector.is_valid_payload({"eventSource": "random.amazonaws.com", "eventName": "Create"}) is True
    assert connector.is_valid_payload({"eventSource": "random.amazonaws.com", "eventName": "Random"}) is True
    assert connector.is_valid_payload({"eventSource": "random.amazonaws.com", "eventName": "GetRecords"}) is False

    assert connector.is_valid_payload({"eventSource": "ec2.amazonaws.com", "eventName": "DescribeInstances"}) is False
    assert connector.is_valid_payload({"eventSource": "ec2.amazonaws.com", "eventName": "CreateImage"}) is True
    assert connector.is_valid_payload({"eventSource": "ec2.amazonaws.com", "eventName": "DescribeTags"}) is False
    assert connector.is_valid_payload({"eventSource": "ec2.amazonaws.com", "eventName": "CreateTags"}) is False


def test_check_if_payload_is_valid_2(connector: AwsS3RecordsTrigger, session_faker: Faker):
    """
    Test AwsS3RecordsTrigger `is_valid_payload`.

    Args:
        connector: AwsS3RecordsTrigger
        session_faker: Faker
    """
    valid_s3_events_prefixes = [
        "Delete",
        "Create",
        "Copy",
        "Put",
        "Restore",
        "GetObjectTorrent",
        "ListBuckets",
    ]

    invalid_s3_events_prefixes = ["List", "Describe", "Random", "GetObject", "GetObjectTagging"]
    for event in valid_s3_events_prefixes:
        assert (
            connector.is_valid_payload(
                {"eventSource": "s3.amazonaws.com", "eventName": "{0}:{1}".format(event, session_faker.word())}
            )
            is True
        )

        assert connector.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": event}) is True

    for event in invalid_s3_events_prefixes:
        assert (
            connector.is_valid_payload(
                {"eventSource": "s3.amazonaws.com", "eventName": "{0}:{1}".format(event, session_faker.word())}
            )
            is False
        )

        assert connector.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": event}) is False

    valid_default_prefixes = ["Delete", "Create", "Copy", "Put", "Restore", "GetObjectTorrent"]
    invalid_default_prefixes = ["List", "Describe", "GetRecords"]
    for event in valid_default_prefixes:
        assert (
            connector.is_valid_payload(
                {"eventSource": "random.amazonaws.com", "eventName": "{0}:{1}".format(event, session_faker.word())}
            )
            is True
        )

        assert connector.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": event}) is True

    for event in invalid_default_prefixes:
        assert (
            connector.is_valid_payload(
                {"eventSource": "random.amazonaws.com", "eventName": "{0}:{1}".format(event, session_faker.word())}
            )
            is False
        )

        assert connector.is_valid_payload({"eventSource": "random.amazonaws.com", "eventName": event}) is False
