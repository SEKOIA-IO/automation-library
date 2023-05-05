import os
from unittest.mock import Mock, patch

import orjson
import pytest

from aws.base import AWSModule
from aws.s3.trigger_s3_parquet import AWSS3ParquetRecordsTrigger
from tests import mock
from tests.base import aws_regions, s3_mock, sqs_mock


@pytest.fixture
def trigger(symphony_storage):
    module = AWSModule()
    trigger = AWSS3ParquetRecordsTrigger(module=module, data_path=symphony_storage)
    trigger.module.configuration = {
        "aws_access_key": "access_key",
        "aws_secret_access_key": "secret_key",
        "aws_region_name": "eu-west-2",
    }
    trigger.configuration = {
        "frequency": 0,
        "queue_name": "cloudtrail-events",
        "intake_key": "1234567890",
    }
    trigger.push_events_to_intakes = Mock()
    trigger.log = Mock()
    trigger.log_exception = Mock()
    yield trigger


# flake8: noqa

S3Objects = {
    "AWSLogs/aws-account-id=111111111111/aws-service=vpcflowlogs/aws-region=eu-west-3/year=2022/month=08/day=31/111111111111_vpcflowlogs_eu-west-3_fl-032a163fae170ae52_20220831T1255Z_2ad4bef5.log.parquet": open(
        "tests/data/111111111111_vpcflowlogs_eu-west-3_fl-032a163fae170ae52_20220831T1255Z_2ad4bef5.parquet",
        "rb",
    ).read(),
}

# flake8: qa

S3Mock = s3_mock(S3Objects)


SQSMessages = [
    '{"Records":[{"eventVersion":"2.1","eventSource":"aws:s3","awsRegion":"eu-west-2","eventTime":"2022-06-27T16:17:56.712Z","eventName":"ObjectCreated:Put","userIdentity":{"principalId":"AWS:AROAJ6N5EQDKQTHMBI5GS:regionalDeliverySession"},"requestParameters":{"sourceIPAddress":"52.56.67.70"},"responseElements":{"x-amz-request-id":"D4M2F8DTSQVJRX7C","x-amz-id-2":"HFot7T6fvHiCaoyE2K/J/uRDPqoDlYOE8vBGZmc/I9Wc+U7RgOrA4qYLaxjbPEnCb1XW4MnrOQ8+AZoCeBJVR53QY1UEN4VT"},"s3":{"s3SchemaVersion":"1.0","configurationId":"FlowLogs","bucket":{"name":"aws-cloudtrail-111111111111-3abc4c4f","ownerIdentity":{"principalId":"A2ZXD4XGWPNOQ9"},"arn":"arn:aws:s3:::aws-cloudtrail-111111111111-3abc4c4f"},"object":{"key":"AWSLogs/aws-account-id=111111111111/aws-service=vpcflowlogs/aws-region=eu-west-3/year=2022/month=08/day=31/111111111111_vpcflowlogs_eu-west-3_fl-032a163fae170ae52_20220831T1255Z_2ad4bef5.log.parquet","size":9234,"eTag":"0cdef8885755dff42b6fbd91732ae506","sequencer":"0062B9D834A809629F"}}}]}',
]


SQSMock = sqs_mock(SQSMessages)

expected_records = [
    {
        "version": 2,
        "account_id": "111111111111",
        "interface_id": "eni-03ef80ddb18bc0997",
        "srcaddr": "64.62.197.99",
        "dstaddr": "172.31.17.39",
        "srcport": 58938,
        "dstport": 20547,
        "protocol": 6,
        "packets": 1,
        "bytes": 40,
        "start": 1661950735,
        "end": 1661950746,
        "action": "REJECT",
        "log_status": "OK",
    },
    {
        "version": 2,
        "account_id": "111111111111",
        "interface_id": "eni-03ef80ddb18bc0997",
        "srcaddr": "172.31.17.39",
        "dstaddr": "78.197.123.35",
        "srcport": 4712,
        "dstport": 53198,
        "protocol": 6,
        "packets": 13,
        "bytes": 2662,
        "start": 1661950735,
        "end": 1661950746,
        "action": "ACCEPT",
        "log_status": "OK",
    },
    {
        "version": 2,
        "account_id": "111111111111",
        "interface_id": "eni-03ef80ddb18bc0997",
        "srcaddr": "78.197.123.35",
        "dstaddr": "172.31.17.39",
        "srcport": 53198,
        "dstport": 4712,
        "protocol": 6,
        "packets": 18,
        "bytes": 4560,
        "start": 1661950735,
        "end": 1661950746,
        "action": "ACCEPT",
        "log_status": "OK",
    },
    {
        "version": 2,
        "account_id": "111111111111",
        "interface_id": "eni-03ef80ddb18bc0997",
        "srcaddr": "167.94.138.130",
        "dstaddr": "172.31.17.39",
        "srcport": 46076,
        "dstport": 8849,
        "protocol": 6,
        "packets": 1,
        "bytes": 44,
        "start": 1661950735,
        "end": 1661950746,
        "action": "REJECT",
        "log_status": "OK",
    },
    {
        "version": 2,
        "account_id": "111111111111",
        "interface_id": "eni-03ef80ddb18bc0997",
        "srcaddr": "78.197.123.35",
        "dstaddr": "172.31.17.39",
        "srcport": 53205,
        "dstport": 4712,
        "protocol": 6,
        "packets": 18,
        "bytes": 4560,
        "start": 1661950735,
        "end": 1661950746,
        "action": "ACCEPT",
        "log_status": "OK",
    },
    {
        "version": 2,
        "account_id": "111111111111",
        "interface_id": "eni-03ef80ddb18bc0997",
        "srcaddr": "124.234.182.240",
        "dstaddr": "172.31.17.39",
        "srcport": 53094,
        "dstport": 2323,
        "protocol": 6,
        "packets": 1,
        "bytes": 40,
        "start": 1661950735,
        "end": 1661950746,
        "action": "REJECT",
        "log_status": "OK",
    },
    {
        "version": 2,
        "account_id": "111111111111",
        "interface_id": "eni-03ef80ddb18bc0997",
        "srcaddr": "172.31.17.39",
        "dstaddr": "78.197.123.35",
        "srcport": 4712,
        "dstport": 53205,
        "protocol": 6,
        "packets": 12,
        "bytes": 2610,
        "start": 1661950735,
        "end": 1661950746,
        "action": "ACCEPT",
        "log_status": "OK",
    },
]


def test_forward_next_batches(trigger, aws_mock, symphony_storage):

    with mock.client.handler_for("s3", S3Mock), mock.client.handler_for("sqs", SQSMock):
        trigger.forward_next_batches()
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls) == 1
        assert [record for call in calls for record in call] == [
            orjson.dumps(record).decode("utf-8") for record in expected_records
        ]


@pytest.mark.skipif(
    "{'AWS_API_KEY', 'AWS_API_SECRET_KEY', 'AWS_QUEUE_NAME', \
            'AWS_REGION'}.issubset(os.environ.keys()) == False"
)
def test_forward_next_batches_integration(symphony_storage):
    module = AWSModule()
    trigger = AWSS3ParquetRecordsTrigger(module=module, data_path=symphony_storage)
    trigger.module.configuration = {
        "aws_access_key": os.environ["AWS_API_KEY"],
        "aws_secret_access_key": os.environ["AWS_API_SECRET_KEY"],
        "aws_region_name": os.environ["AWS_REGION"],
    }
    trigger.configuration = {
        "frequency": 0,
        "queue_name": os.environ["AWS_QUEUE_NAME"],
        "intake_key": "1234567890",
    }
    trigger.push_events_to_intakes = Mock()
    trigger.log = Mock()
    trigger.log_exception = Mock()
    trigger.forward_next_batches()
    calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
    assert len(calls) > 0
