from ipaddress import ip_address
import os
from unittest.mock import Mock, patch

import pytest

from aws.base import AWSModule
from aws.s3.trigger_s3_flowlogs import AWSS3FlowLogsTrigger
from tests import mock
from tests.base import S3MockNoContent, S3MockNoObject, SQSMockNoContent, s3_mock, sqs_mock


@pytest.fixture
def trigger(symphony_storage):
    module = AWSModule()
    trigger = AWSS3FlowLogsTrigger(module=module, data_path=symphony_storage)
    trigger.module.configuration = {
        "aws_access_key": "access_key",
        "aws_secret_access_key": "secret_key",
        "aws_region_name": "eu-west-2",
    }
    trigger.configuration = {
        "frequency": 0,
        "queue_name": "vpcflowlogs-events",
        "separator": "\n",
        "skip_first": 0,
        "ignore_comments": True,
        "intake_key": "1234567890",
    }
    trigger.push_events_to_intakes = Mock()
    trigger.log = Mock()
    trigger.log_exception = Mock()
    yield trigger


# flake8: noqa
S3Objects = {
    "AWSLogs/111111111111/vpcflowlogs/eu-west-2/2022/02/21/111111111111_vpcflowlogs_eu-west-2_fl-0dcbf7c4c2483c6b6_20220221T1955Z_7fe2e5f7.log.gz": b"""version account-id interface-id srcaddr dstaddr srcport dstport protocol packets bytes start end action log-status

2 111111111111 eni-0a479835a7588c9ca 79.124.62.82 172.31.39.167 58757 39045 6 1 40 1645469669 1645469724 REJECT OK
2 111111111111 eni-0a479835a7588c9ca 172.31.39.167 188.114.116.1 44789 123 17 1 76 1645469669 1645469724 ACCEPT OK
2 111111111111 eni-0a479835a7588c9ca 45.79.182.177 172.31.39.167 61000 465 6 1 40 1645469669 1645469724 REJECT OK
2 111111111111 eni-0a479835a7588c9ca 188.114.116.1 172.31.39.167 123 44789 17 1 76 1645469669 1645469724 ACCEPT OK
2 111111111111 eni-0a479835a7588c9ca 172.31.39.166 172.31.39.167 123 44789 17 1 76 1645469669 1645469724 ACCEPT OK
2 111111111111 eni-0a479835a7588c9ca 223.71.167.166 172.31.39.167 10211 10001 17 1 32 1645469669 1645469724 REJECT OK""",
    "AWSLogs/111111111111/vpcflowlogs/eu-west-2/2022/02/21/111111111111_vpcflowlogs_eu-west-2_fl-0dcbf7c4c2483c6b6_20220221T2025Z_55a7d2af.log.gz": b"""version account-id interface-id srcaddr dstaddr srcport dstport protocol packets bytes start end action log-status
2 111111111111 eni-0a479835a7588c9ca 92.63.196.61 172.31.39.167 41147 3148 6 1 40 1645475075 1645475129 REJECT OK
2 111111111111 eni-0a479835a7588c9ca 45.79.134.162 172.31.39.167 61000 994 6 1 40 1645475075 1645475129 REJECT OK
2 111111111111 eni-0a479835a7588c9ca 94.232.45.43 172.31.39.167 49968 3138 6 1 40 1645475075 1645475129 REJECT OK
2 111111111111 eni-0a479835a7588c9ca 50.116.61.127 172.31.39.167 61000 110 6 1 40 1645475075 1645475129 REJECT OK
2 111111111111 eni-0a479835a7588c9ca 172.31.39.165 172.31.39.167 61000 110 6 1 40 1645475075 1645475129 REJECT OK
2 111111111111 eni-0a479835a7588c9ca 92.63.197.14 172.31.39.167 44713 8990 6 1 40 1645475075 1645475129 REJECT OK""",
}
# flake8: qa

S3Mock = s3_mock(S3Objects)

SQSMessages = [
    '{"Records":[{"eventVersion":"2.1","eventSource":"aws:s3","awsRegion":"eu-west-2","eventTime":"2022-06-27T16:17:56.712Z","eventName":"ObjectCreated:Put","userIdentity":{"principalId":"AWS:AROAJ6N5EQDKQTHMBI5GS:regionalDeliverySession"},"requestParameters":{"sourceIPAddress":"52.56.67.70"},"responseElements":{"x-amz-request-id":"D4M2F8DTSQVJRX7C","x-amz-id-2":"HFot7T6fvHiCaoyE2K/J/uRDPqoDlYOE8vBGZmc/I9Wc+U7RgOrA4qYLaxjbPEnCb1XW4MnrOQ8+AZoCeBJVR53QY1UEN4VT"},"s3":{"s3SchemaVersion":"1.0","configurationId":"FlowLogs","bucket":{"name":"aws-vpcflowlogs-111111111111-3abc4c4f","ownerIdentity":{"principalId":"A2ZXD4XGWPNOQ9"},"arn":"arn:aws:s3:::aws-vpcflowlogs-111111111111-3abc4c4f"},"object":{"key":"AWSLogs/111111111111/vpcflowlogs/eu-west-2/2022/02/21/111111111111_vpcflowlogs_eu-west-2_fl-0dcbf7c4c2483c6b6_20220221T1955Z_7fe2e5f7.log.gz","size":9234,"eTag":"0cdef8885755dff42b6fbd91732ae506","sequencer":"0062B9D834A809629F"}}}]}',
    '{"Service":"Amazon S3","Event":"s3:TestEvent","Time":"2022-06-27T16:14:56.447Z","Bucket":"aws-cloudtrail-logs-111111111111-3abc4c4f","RequestId":"JGMN6V8XHKTYJS5J","HostId":"Ea/gza8Js+dQmg+1DUhIX46sdeYZMBEMJJ5Vo9pZlmh6giANwm2cELcoRcCcQdgfcZmtK81b+p4="}',
    '{"Records":[{"eventVersion":"2.1","eventSource":"aws:s3","awsRegion":"eu-west-2","eventTime":"2022-06-27T16:19:22.631Z","eventName":"ObjectCreated:Put","userIdentity":{"principalId":"AWS:AROAJ6N5EQDKQTHMBI5GS:regionalDeliverySession"},"requestParameters":{"sourceIPAddress":"34.195.91.227"},"responseElements":{"x-amz-request-id":"3579M4QA3X2863DM","x-amz-id-2":"mqqIkQwXY7tryvk5DNHgFtP459rD9pJcXlUDwDg6/BgYy1GpfVf97jSxXYu3FF4zqfQloVtmLuXYHNMupXHiYVxaKDpg32cS"},"s3":{"s3SchemaVersion":"1.0","configurationId":"FlowLogs","bucket":{"name":"aws-vpcflowlogs-111111111111-3abc4c4f","ownerIdentity":{"principalId":"A2ZXD4XGWPNOQ9"},"arn":"arn:aws:s3:::aws-vpcflowlogs-111111111111-3abc4c4f"},"object":{"key":"AWSLogs/111111111111/vpcflowlogs/eu-west-2/2022/02/21/111111111111_vpcflowlogs_eu-west-2_fl-0dcbf7c4c2483c6b6_20220221T2025Z_55a7d2af.log.gz","size":1084,"eTag":"54a88e9fdedaeda828710cd3ad23a83c","sequencer":"0062B9D88A7DF00CB0"}}}]}',
]

SQSMock = sqs_mock(SQSMessages)


def test_get_next_log_file(trigger, aws_mock):
    with mock.client.handler_for("s3", S3Mock), mock.client.handler_for("sqs", SQSMock):
        assert [obj.key for obj in trigger.get_next_objects(trigger.get_next_messages())] == list(S3Objects.keys())


def test_forward_next_batches(trigger, aws_mock, symphony_storage):
    with mock.client.handler_for("s3", S3Mock), mock.client.handler_for("sqs", SQSMock):
        trigger.forward_next_batches()
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls) == 2

        assert [record for call in calls for record in call] == [
            record
            for obj in S3Objects.values()
            for record in obj.decode("utf-8").split("\n")[1:]
            if len(record) > 0 and
               not (ip_address(record.split(" ")[3]).is_private and ip_address(record.split(" ")[4]).is_private)
        ]


def test_forward_next_batches_with_no_message(trigger, aws_mock, symphony_storage):
    with mock.client.handler_for("s3", S3Mock), mock.client.handler_for("sqs", SQSMockNoContent):
        trigger.forward_next_batches()
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls) == 0


def test_forward_next_batches_with_no_content(trigger, aws_mock, symphony_storage):
    with mock.client.handler_for("s3", S3MockNoContent), mock.client.handler_for("sqs", SQSMock):
        trigger.forward_next_batches()
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls) == 0


def test_forward_next_batches_with_no_object(trigger, aws_mock, symphony_storage):
    with mock.client.handler_for("s3", S3MockNoObject), mock.client.handler_for("sqs", SQSMock):
        trigger.forward_next_batches()
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls) == 0


# flake8: noqa

S3ObjectsNoRecords = {
    "AWSLogs/111111111111/vpcflowlogs/eu-west-2/2022/02/21/111111111111_vpcflowlogs_eu-west-2_fl-0dcbf7c4c2483c6b6_20220221T1955Z_7fe2e5f7.log.gz": b"",
    "AWSLogs/111111111111/vpcflowlogs/eu-west-2/2022/02/21/111111111111_vpcflowlogs_eu-west-2_fl-0dcbf7c4c2483c6b6_20220221T2025Z_55a7d2af.log.gz": b"",
}

SQSNoJson = ["Not a json"]
SQSNoJsonMock = sqs_mock(SQSNoJson)


def test_batch_not_json(trigger, aws_mock, symphony_storage):
    with mock.client.handler_for("s3", S3MockNoObject), mock.client.handler_for("sqs", SQSNoJsonMock):
        trigger.forward_next_batches()


# flake8: qa

S3MockNoRecords = s3_mock(S3ObjectsNoRecords)


def test_forward_next_batches_with_no_records(trigger, aws_mock, symphony_storage):
    with mock.client.handler_for("s3", S3MockNoRecords), mock.client.handler_for("sqs", SQSMock):
        trigger.forward_next_batches()
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls) == 0


@pytest.mark.skipif(
    "{'AWS_API_KEY', 'AWS_API_SECRET_KEY', 'AWS_QUEUE_NAME', \
            'AWS_REGION'}.issubset(os.environ.keys()) == False"
)
def test_forward_next_batches_integration(symphony_storage):
    module = AWSModule()
    trigger = AWSS3FlowLogsTrigger(module=module, data_path=symphony_storage)
    trigger.module.configuration = {
        "aws_access_key": os.environ["AWS_API_KEY"],
        "aws_secret_access_key": os.environ["AWS_API_SECRET_KEY"],
        "aws_region_name": os.environ["AWS_REGION"],
    }
    trigger.configuration = {
        "frequency": 0,
        "queue_name": os.environ["AWS_QUEUE_NAME"],
        "separator": "\n",
        "skip_first": 1,
        "intake_key": "1234567890",
    }
    trigger.push_events_to_intakes = Mock()
    trigger.log = Mock()
    trigger.log_exception = Mock()
    trigger.forward_next_batches()
    calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
    assert len(calls) > 0
