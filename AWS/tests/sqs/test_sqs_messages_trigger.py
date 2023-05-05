import os
from unittest.mock import Mock

import pytest

from aws.base import AWSModule
from aws.sqs.trigger_sqs_messages import AWSSQSMessagesTrigger
from tests import mock
from tests.base import sqs_mock


@pytest.fixture
def trigger(symphony_storage):
    module = AWSModule()
    trigger = AWSSQSMessagesTrigger(module=module, data_path=symphony_storage)
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
SQSMessages = [
    '{"Records":[{"eventVersion":"2.1","eventSource":"aws:s3","awsRegion":"eu-west-2","eventTime":"2022-06-27T16:17:56.712Z","eventName":"ObjectCreated:Put","userIdentity":{"principalId":"AWS:AROAJ6N5EQDKQTHMBI5GS:regionalDeliverySession"},"requestParameters":{"sourceIPAddress":"52.56.67.70"},"responseElements":{"x-amz-request-id":"D4M2F8DTSQVJRX7C","x-amz-id-2":"HFot7T6fvHiCaoyE2K/J/uRDPqoDlYOE8vBGZmc/I9Wc+U7RgOrA4qYLaxjbPEnCb1XW4MnrOQ8+AZoCeBJVR53QY1UEN4VT"},"s3":{"s3SchemaVersion":"1.0","configurationId":"FlowLogs","bucket":{"name":"aws-cloudtrail-111111111111-3abc4c4f","ownerIdentity":{"principalId":"A2ZXD4XGWPNOQ9"},"arn":"arn:aws:s3:::aws-cloudtrail-111111111111-3abc4c4f"},"object":{"key":"AWSLogs/aws-account-id=111111111111/aws-service=vpcflowlogs/aws-region=eu-west-3/year=2022/month=08/day=31/111111111111_vpcflowlogs_eu-west-3_fl-032a163fae170ae52_20220831T1255Z_2ad4bef5.log.parquet","size":9234,"eTag":"0cdef8885755dff42b6fbd91732ae506","sequencer":"0062B9D834A809629F"}}}]}',
]
# flake8: qa


SQSMock = sqs_mock(SQSMessages)


def test_forward_next_batches(trigger, aws_mock, symphony_storage):

    with mock.client.handler_for("sqs", SQSMock):
        trigger.forward_next_batches()
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls) == 1


@pytest.mark.skipif(
    "{'AWS_API_KEY', 'AWS_API_SECRET_KEY', 'AWS_QUEUE_NAME', \
            'AWS_REGION'}.issubset(os.environ.keys()) == False"
)
def test_forward_next_batches_integration(symphony_storage):
    module = AWSModule()
    trigger = AWSSQSMessagesTrigger(module=module, data_path=symphony_storage)
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
