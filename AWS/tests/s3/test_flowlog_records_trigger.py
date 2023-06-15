import os
import re
from unittest.mock import Mock, patch

import orjson
import pytest

from aws.base import AWSModule
from aws.s3.trigger_flowlog_records import FlowlogRecordsTrigger, FlowlogRecordsWorker
from tests import mock
from tests.base import S3_REGIONS, S3MockNoContent, STSMock, aws_regions, s3_mock
from tests.utils import read_file


@pytest.fixture
def trigger(symphony_storage):
    module = AWSModule()
    trigger = FlowlogRecordsTrigger(module=module, data_path=symphony_storage)
    trigger.module.configuration = {
        "aws_access_key": "access_key",
        "aws_secret_access_key": "secret_key",
        "aws_region_name": "eu-west-2",
    }
    trigger.configuration = {
        "frequency": 1,
        "bucket_name": "aws-cloudtrail-logs-111111111111-3abc4c4f",
        "intake_key": "1234567890",
    }
    trigger.send_event = Mock()
    trigger.log = Mock()
    trigger.log_exception = Mock()
    yield trigger


@pytest.fixture
def prefix(trigger):
    return "AWSLogs/111111111111/vpcflowlogs/eu-west-2/"


@pytest.fixture
def worker(trigger, prefix):
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


def test_fetch_next_objects(worker, aws_mock):
    with mock.client.handler_for("s3", S3Mock):
        assert list(worker._fetch_next_objects(marker=None)) == list(S3Objects.keys())


def test_forward_events(worker, trigger, aws_mock, symphony_storage):
    with mock.client.handler_for("s3", S3Mock):
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


def test_forward_events_with_no_content(worker, trigger, aws_mock):
    with mock.client.handler_for("s3", S3MockNoContent):
        worker.forward_events()
        calls = {
            call.kwargs["event_name"]: call.kwargs.get("event")
            for call in trigger.send_event.call_args_list
            if call.kwargs.get("event_name")
        }
        assert trigger.send_event.called is False
        assert trigger.log_exception.called is False


@pytest.mark.skipif(
    "{'AWS_API_KEY', 'AWS_API_SECRET_KEY', 'AWS_BUCKET_NAME', \
            'AWS_REGION'}.issubset(os.environ.keys()) == False"
)
def test_forward_events_integration(symphony_storage, worker):
    module = AWSModule()
    trigger = FlowlogRecordsTrigger(module=module, data_path=symphony_storage)
    trigger.module.configuration = {
        "aws_access_key": os.environ["AWS_API_KEY"],
        "aws_secret_access_key": os.environ["AWS_API_SECRET_KEY"],
        "aws_region_name": os.environ["AWS_REGION"],
    }
    trigger.configuration = {
        "frequency": 604800,
        "bucket_name": os.environ["AWS_BUCKET_NAME"],
        "intake_key": "1234567890",
    }

    prefix = os.environ.get("AWS_PREFIX")
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
    assert len(calls) > 0
    assert all([name.startswith("aws-flowlog_") for name in calls.keys()])
    assert all(
        isinstance(record, str)
        for call in calls.values()
        for record in read_file(symphony_storage, call["directory"], call["event"]["records_path"])
    )


def test_prefixes(symphony_storage, trigger, aws_mock):
    with mock.region.handler_for("ec2", aws_regions), mock.client.handler_for("sts", STSMock):
        prefixes = trigger.prefixes()
        assert prefixes == {f"AWSLogs/111111111111/vpcflowlogs/{region}/" for region in S3_REGIONS}


@pytest.mark.skipif(
    "{'AWS_API_KEY', 'AWS_API_SECRET_KEY', 'AWS_BUCKET_NAME', \
            'AWS_REGION'}.issubset(os.environ.keys()) == False"
)
def test_prefixes_integration(symphony_storage, worker):
    module = AWSModule()
    trigger = FlowlogRecordsTrigger(module=module, data_path=symphony_storage)
    trigger.module.configuration = {
        "aws_access_key": os.environ["AWS_API_KEY"],
        "aws_secret_access_key": os.environ["AWS_API_SECRET_KEY"],
        "aws_region_name": os.environ["AWS_REGION"],
    }
    trigger.configuration = {
        "frequency": 1,
        "bucket_name": os.environ["AWS_BUCKET_NAME"],
        "intake_key": "1234567890",
    }
    trigger.log = Mock()
    trigger.log_exception = Mock()

    prefixes = trigger.prefixes()
    assert len(prefixes) > 0
    pattern = re.compile(r"^AWSLogs/\d{12}/vpcflowlogs/[a-z0-9-]+/")
    assert all([pattern.match(prefix) is not None for prefix in prefixes])
