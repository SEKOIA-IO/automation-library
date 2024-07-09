"""Tests for CrowdStrike Telemetry connector."""

import json
from gzip import compress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crowdstrike_telemetry import CrowdStrikeTelemetryModule, CrowdStrikeTelemetryModuleConfig
from crowdstrike_telemetry.pull_telemetry_events import CrowdStrikeTelemetryConfig, CrowdStrikeTelemetryConnector


@pytest.fixture
def pushed_ids(session_faker) -> list[str]:
    """
    Generate random list of events ids.

    Args:
        session_faker: Faker

    Returns:
        list[str]:
    """
    return [session_faker.word() for _ in range(session_faker.random.randint(1, 10))]


@pytest.fixture
def crowdstrike_connector(session_faker, symphony_storage, pushed_ids) -> CrowdStrikeTelemetryConnector:
    """
    Create CrowdStrikeTelemetryConnector instance.

    Args:
        session_faker: Faker
        symphony_storage: str
        pushed_ids: list[str]

    Returns:
        CrowdStrikeTelemetryConnector:
    """
    module = CrowdStrikeTelemetryModule()
    module.configuration = CrowdStrikeTelemetryModuleConfig(
        aws_access_key_id=session_faker.word(),
        aws_secret_access_key=session_faker.word(),
        aws_region=session_faker.word(),
    )

    connector = CrowdStrikeTelemetryConnector(
        module=module,
        data_path=symphony_storage,
    )

    connector.configuration = CrowdStrikeTelemetryConfig(
        intake_server=session_faker.url(),
        queue_name=session_faker.word(),
        intake_key=session_faker.word(),
        chunk_size=session_faker.random.randint(1, 10),
        frequency=session_faker.random.randint(0, 20),
        delete_consumed_messages=True,
        is_fifo=False,
    )
    connector.push_events_to_intakes = MagicMock()
    connector.push_data_to_intakes = AsyncMock(return_value=pushed_ids)
    connector.log = MagicMock()
    connector.log_exception = MagicMock()

    return connector


@pytest.mark.asyncio
async def test_process_s3_file(crowdstrike_connector, session_faker):
    """
    Test process_s3_file method.

    Args:
        crowdstrike_connector: CrowdStrikeTelemetryConnector
        session_faker: Faker
    """
    key = session_faker.file_path(depth=2, extension="json")
    content = b"""
{"data": "aaaaa", "event_simpleName": "EndOfProcess"}
{"data": "bbbbb", "event_simpleName": "FalconServiceStatus"}
"""
    expected = [
        '{"data": "aaaaa", "event_simpleName": "EndOfProcess"}',
    ]

    with patch.object(crowdstrike_connector.s3_wrapper, "read_key") as mock_read_key:
        mock_read_key.return_value.__aenter__.return_value = content

        result = await crowdstrike_connector.process_s3_file(key)

        assert result == expected
        mock_read_key.assert_called_once_with(key, None)


@pytest.mark.asyncio
async def test_process_gzipped_s3_file(crowdstrike_connector, session_faker):
    """
    Test process_s3_file method.

    Args:
        crowdstrike_connector: CrowdStrikeTelemetryConnector
        session_faker: Faker
    """
    key = session_faker.file_path(depth=2, extension="json")
    data = [
        {"data": session_faker.sentence(), "event_simpleName": "EndOfProcess"},
        {"data": session_faker.sentence(), "event_simpleName": "EndOfProcess"},
    ]
    expected = [json.dumps(item) for item in data]

    with patch.object(crowdstrike_connector.s3_wrapper, "read_key") as mock_read_key:
        mock_read_key.return_value.__aenter__.return_value = compress(
            b"\n".join([item.encode("utf-8") for item in expected])
        )

        result = await crowdstrike_connector.process_s3_file(key)

        assert result == expected
        mock_read_key.assert_called_once_with(key, None)


@pytest.mark.asyncio
async def test_process_s3_file_one_line(crowdstrike_connector, session_faker):
    """
    Test process_s3_file method.

    Args:
        crowdstrike_connector: CrowdStrikeTelemetryConnector
        session_faker: Faker
    """
    key = session_faker.file_path(depth=2, extension="json")
    data = {"data": session_faker.sentence(), "event_simpleName": "EndOfProcess"}
    expected = [json.dumps(data)]

    with patch.object(crowdstrike_connector.s3_wrapper, "read_key") as mock_read_key:
        mock_read_key.return_value.__aenter__.return_value = b"\n".join([item.encode("utf-8") for item in expected])

        result = await crowdstrike_connector.process_s3_file(key)

        assert result == expected
        mock_read_key.assert_called_once_with(key, None)


@pytest.mark.asyncio
async def test_get_crowdstrike_events(crowdstrike_connector, session_faker, pushed_ids):
    """
    Test get_crowdstrike_events method.

    Args:
        crowdstrike_connector: CrowdStrikeTelemetryConnector
        session_faker: Faker
        pushed_ids: list[str]
    """
    receipt_handle_1 = session_faker.word()
    receipt_handle_2 = session_faker.word()

    queue_url = session_faker.url()

    expected_response = {
        "Messages": [
            {
                "Body": '{"bucket": "MyBucket", "files": [{"path": "mypath1"}, {"path": "mypath2"}]}',
                "ReceiptHandle": receipt_handle_1,
            },
            {"Body": '{"bucket": "MyBucket", "files": [{"path": "mypath3"}]}', "ReceiptHandle": receipt_handle_2},
        ]
    }

    expected = [
        {"data": session_faker.sentence()},
        {"data": session_faker.sentence()},
    ]

    with (
        patch("aws.sqs.SqsWrapper.get_client") as mock_client,
        patch.object(crowdstrike_connector.s3_wrapper, "read_key") as mock_read_key,
    ):
        mock_sqs = MagicMock()

        mock_sqs.receive_message = AsyncMock()
        mock_sqs.receive_message.return_value = expected_response

        mock_sqs.delete_message = AsyncMock()
        mock_sqs.delete_message.return_value = {}

        mock_sqs.get_queue_url = AsyncMock()
        mock_sqs.get_queue_url.return_value = {"QueueUrl": queue_url}

        mock_client.return_value.__aenter__.return_value = mock_sqs

        mock_read_key.return_value.__aenter__.return_value = b"\n".join(
            [json.dumps(item).encode("utf-8") for item in expected]
        )

        result = await crowdstrike_connector.get_crowdstrike_events()

        assert result == pushed_ids


@pytest.mark.asyncio
async def test_specify_queue_url(session_faker):
    queue_url = session_faker.url()

    module = CrowdStrikeTelemetryModule()
    module.configuration = CrowdStrikeTelemetryModuleConfig(
        aws_access_key_id=session_faker.word(),
        aws_secret_access_key=session_faker.word(),
        aws_region=session_faker.word(),
    )

    connector = CrowdStrikeTelemetryConnector(
        module=module,
    )
    connector.configuration = CrowdStrikeTelemetryConfig(
        queue_name=session_faker.word(),
        queue_url=queue_url,
        intake_key=session_faker.word(),
        chunk_size=session_faker.random.randint(1, 10),
        frequency=session_faker.random.randint(0, 20),
        delete_consumed_messages=True,
        is_fifo=False,
    )
    connector.push_events_to_intakes = MagicMock()
    connector.log = MagicMock()
    connector.log_exception = MagicMock()

    sqs_wrapper = connector.sqs_wrapper
    assert await sqs_wrapper.queue_url() == queue_url
