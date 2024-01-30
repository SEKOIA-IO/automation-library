"""Tests related to FlowlogRecordsTrigger."""

import re
from pathlib import Path
from unittest.mock import Mock

import pytest
from faker import Faker

from connectors import AwsModule
from connectors.s3.logs.trigger_flowlog_records import FlowlogRecordsTrigger, FlowlogRecordsWorker

from .base import S3_REGIONS, S3MockNoContent, STSMock, aws_regions, read_file, s3_mock
from .mock import mocked_client, mocked_region


@pytest.fixture
def trigger(faker: Faker, symphony_storage: Path, aws_module: AwsModule) -> FlowlogRecordsTrigger:
    """
    Create a FlowlogRecordsTrigger.

    Args:
        faker: Faker
        symphony_storage: Path
        aws_module: AwsModule

    Returns:
        FlowlogRecordsTrigger:
    """
    flowlog_records_trigger = FlowlogRecordsTrigger(module=aws_module, data_path=symphony_storage)

    flowlog_records_trigger.configuration = {
        "frequency": faker.pyint(min_value=1, max_value=10),
        "bucket_name": faker.word(),
        "intake_key": faker.word(),
    }

    flowlog_records_trigger.send_event = Mock()
    flowlog_records_trigger.log = Mock()
    flowlog_records_trigger.log_exception = Mock()

    return flowlog_records_trigger


@pytest.fixture
def prefix(faker: Faker, trigger: FlowlogRecordsTrigger) -> str:
    """
    Create a prefix.

    Args:
        faker: Faker
        trigger: FlowlogRecordsTrigger

    Returns:
        str:
    """
    result = faker.word()

    trigger.configuration.prefix = prefix

    return result


@pytest.fixture
def worker(trigger: FlowlogRecordsTrigger, prefix: str) -> FlowlogRecordsWorker:
    """
    Create a FlowlogRecordsWorker.

    Returns:
        FlowlogRecordsWorker:
    """
    return FlowlogRecordsWorker(trigger, prefix)


# flake8: noqa
S3Objects = {
    "AWSLogs/111111111111/vpcflowlogs/eu-west-2/2022/02/21/111111111111_vpcflowlogs_eu-west-2_fl-0dcbf7c4c2483c6b6_20220221T1955Z_7fe2e5f7.log.gz": b"""version account-id interface-id srcaddr dstaddr srcport dstport protocol packets bytes start end action log-status
2 111111111111 eni-0a479835a7588c9ca 79.124.62.82 172.31.39.167 58757 39045 6 1 40 1645469669 1645469724 REJECT OK
2 111111111111 eni-0a479835a7588c9ca 172.31.39.167 188.114.116.1 44789 123 17 1 76 1645469669 1645469724 ACCEPT OK
2 111111111111 eni-0a479835a7588c9ca 45.79.182.177 172.31.39.167 61000 465 6 1 40 1645469669 1645469724 REJECT OK
2 111111111111 eni-0a479835a7588c9ca 188.114.116.1 172.31.39.167 123 44789 17 1 76 1645469669 1645469724 ACCEPT OK
2 111111111111 eni-0a479835a7588c9ca 223.71.167.166 172.31.39.167 10211 10001 17 1 32 1645469669 1645469724 REJECT OK""",
    "AWSLogs/111111111111/vpcflowlogs/eu-west-2/2022/02/21/111111111111_vpcflowlogs_eu-west-2_fl-0dcbf7c4c2483c6b6_20220221T2025Z_55a7d2af.log.gz": b"""version account-id interface-id srcaddr dstaddr srcport dstport protocol packets bytes start end action log-status
2 111111111111 eni-0a479835a7588c9ca 92.63.196.61 172.31.39.167 41147 3148 6 1 40 1645475075 1645475129 REJECT OK
2 111111111111 eni-0a479835a7588c9ca 45.79.134.162 172.31.39.167 61000 994 6 1 40 1645475075 1645475129 REJECT OK
2 111111111111 eni-0a479835a7588c9ca 94.232.45.43 172.31.39.167 49968 3138 6 1 40 1645475075 1645475129 REJECT OK
2 111111111111 eni-0a479835a7588c9ca 50.116.61.127 172.31.39.167 61000 110 6 1 40 1645475075 1645475129 REJECT OK
2 111111111111 eni-0a479835a7588c9ca 92.63.197.14 172.31.39.167 44713 8990 6 1 40 1645475075 1645475129 REJECT OK""",
}
# flake8: qa

S3Mock = s3_mock(S3Objects)


def test_fetch_next_objects(worker: FlowlogRecordsWorker, aws_mock):
    """
    Test the fetch next objects.

    Args:
        worker: FlowlogRecordsWorker
        aws_mock:
    """
    with mocked_client.handler_for("s3", S3Mock):
        assert list(worker._fetch_next_objects(marker=None)) == list(S3Objects.keys())


def test_forward_events(
    worker: FlowlogRecordsWorker, trigger: FlowlogRecordsTrigger, symphony_storage: Path, aws_mock
):
    """
    Test the forward events.

    Args:
        worker: FlowlogRecordsWorker
        trigger: FlowlogRecordsTrigger
        symphony_storage: Path
        aws_mock:
    """
    with mocked_client.handler_for("s3", S3Mock):
        worker.forward_events()
        calls = {
            call.kwargs["event_name"]: call.kwargs
            for call in trigger.send_event.call_args_list
            if call.kwargs.get("event_name")
        }
        assert len(calls) == 1
        assert all([name.startswith("aws-flowlog_") for name in calls.keys()])
        assert [
            record
            for call in calls.values()
            for record in read_file(symphony_storage, call["directory"], call["event"]["records_path"])
        ] == [record for obj in S3Objects.values() for record in obj.decode("utf-8").split("\n")[1:]]


def test_forward_events_with_no_content(trigger: FlowlogRecordsTrigger, worker: FlowlogRecordsWorker, aws_mock):
    """
    Test the forward events with no content.

    Args:
        trigger: FlowlogRecordsTrigger
        worker: FlowlogRecordsWorker
        aws_mock:
    """
    with mocked_client.handler_for("s3", S3MockNoContent):
        worker.forward_events()
        calls = {
            call.kwargs["event_name"]: call.kwargs.get("event")
            for call in trigger.send_event.call_args_list
            if call.kwargs.get("event_name")
        }
        assert trigger.send_event.called is False
        assert trigger.log_exception.called is False


def test_forward_events_integration(faker: Faker, aws_module: AwsModule, symphony_storage: Path):
    """
    Test the forward events integration.

    Args:
        faker: Faker
        aws_module: AwsModule
        symphony_storage: Path
    """
    trigger = FlowlogRecordsTrigger(module=aws_module, data_path=symphony_storage)

    trigger.configuration = {
        "frequency": faker.pyint(min_value=1, max_value=10),
        "bucket_name": faker.word(),
        "intake_key": faker.word(),
    }

    prefix = faker.word()
    if prefix:
        trigger.configuration.prefix = prefix

    trigger.send_event = Mock()
    trigger.log = Mock()
    trigger.log_exception = Mock()

    worker = FlowlogRecordsWorker(trigger, prefix)
    worker.forward_events()
    calls = {
        call.kwargs["event_name"]: call.kwargs
        for call in trigger.send_event.call_args_list
        if call.kwargs.get("event_name")
    }

    assert all([name.startswith("aws-flowlog_") for name in calls.keys()])
    assert all(
        isinstance(record, str)
        for call in calls.values()
        for record in read_file(symphony_storage, call["directory"], call["event"]["records_path"])
    )


def test_prefixes(trigger: FlowlogRecordsTrigger, symphony_storage: Path, aws_mock):
    """
    Test the prefixes.

    Args:
        trigger: FlowlogRecordsTrigger
        symphony_storage: Path
        aws_mock:
    """
    with mocked_region.handler_for("ec2", aws_regions), mocked_client.handler_for("sts", STSMock):
        prefixes = trigger.prefixes()
        assert prefixes == {f"AWSLogs/111111111111/vpcflowlogs/{region}/" for region in S3_REGIONS}


def test_prefixes_integration(faker: Faker, aws_module: AwsModule, symphony_storage: Path, aws_mock):
    """
    Test the prefixes integration.

    Args:
        faker: Faker
        aws_module: AwsModule
        symphony_storage: Path
        aws_mock:
    """
    with mocked_region.handler_for("ec2", aws_regions), mocked_client.handler_for("sts", STSMock):
        trigger = FlowlogRecordsTrigger(module=aws_module, data_path=symphony_storage)

        trigger.configuration = {
            "frequency": faker.pyint(min_value=1, max_value=10),
            "bucket_name": faker.word(),
            "intake_key": faker.word(),
        }
        trigger.log = Mock()
        trigger.log_exception = Mock()

        prefixes = trigger.prefixes()
        assert len(prefixes) > 0
        pattern = re.compile(r"^AWSLogs/\d{12}/vpcflowlogs/[a-z0-9-]+/")
        assert all([pattern.match(prefix) is not None for prefix in prefixes])
