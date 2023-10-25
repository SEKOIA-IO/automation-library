import os
from unittest.mock import Mock, patch

import orjson
import pytest

from aws.base import AWSModule
from aws.s3.trigger_s3_records import AWSS3RecordsTrigger
from tests import mock
from tests.base import S3MockNoContent, S3MockNoObject, SQSMockNoContent, aws_regions, s3_mock, sqs_mock


@pytest.fixture
def trigger(symphony_storage):
    module = AWSModule()
    trigger = AWSS3RecordsTrigger(module=module, data_path=symphony_storage)
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
    "AWSLogs/111111111111/CloudTrail/eu-west-2/2022/02/21/111111111111_CloudTrail_eu-west-2_20220221T1020Z_nTGkKkyO0OcwEIvv.json.gz": orjson.dumps(
        {
            "Records": [
                {
                    "eventVersion": "1.08",
                    "userIdentity": {
                        "type": "Root",
                        "principalId": "111111111111",
                        "arn": "arn:aws:iam::111111111111:root",
                        "accountId": "111111111111",
                        "accessKeyId": "ASIAUR6F6MOZQTDOKOWO",
                        "sessionContext": {
                            "sessionIssuer": {},
                            "webIdFederationData": {},
                            "attributes": {
                                "creationDate": "2022-02-21T09:06:22Z",
                                "mfaAuthenticated": "False",
                            },
                        },
                    },
                    "eventTime": "2022-02-21T10:11:11Z",
                    "eventSource": "ec2.amazonaws.com",
                    "eventName": "Put",
                    "awsRegion": "eu-west-2",
                    "sourceIPAddress": "78.197.123.35",
                    "userAgent": "console.ec2.amazonaws.com",
                    "requestParameters": {
                        "accountAttributeNameSet": {"items": [{"attributeName": "supported-platforms"}]},
                        "filterSet": {},
                    },
                    "responseElements": None,
                    "requestID": "e3725315-2824-4f73-9d74-e40a1ee1a809",
                    "eventID": "414cdb47-e739-4842-9d13-ddbe947a61f9",
                    "readOnly": True,
                    "eventType": "AwsApiCall",
                    "managementEvent": True,
                    "recipientAccountId": "111111111111",
                    "eventCategory": "Management",
                    "sessionCredentialFromConsole": "True",
                },
                {
                    "eventVersion": "1.08",
                    "userIdentity": {
                        "type": "Root",
                        "principalId": "111111111111",
                        "arn": "arn:aws:iam::111111111111:root",
                        "accountId": "111111111111",
                        "accessKeyId": "ASIAUR6F6MOZQTDOKOWO",
                        "sessionContext": {
                            "sessionIssuer": {},
                            "webIdFederationData": {},
                            "attributes": {
                                "creationDate": "2022-02-21T09:06:22Z",
                                "mfaAuthenticated": "False",
                            },
                        },
                    },
                    "eventTime": "2022-02-21T10:11:11Z",
                    "eventSource": "ec2.amazonaws.com",
                    "eventName": "Delete",
                    "awsRegion": "eu-west-2",
                    "sourceIPAddress": "78.197.123.35",
                    "userAgent": "console.ec2.amazonaws.com",
                    "requestParameters": {
                        "instancesSet": {},
                        "filterSet": {},
                        "includeAllInstances": False,
                    },
                    "responseElements": None,
                    "requestID": "8733d003-3e0d-4c30-bb45-6a9815c389fb",
                    "eventID": "e35394be-60a9-4ebc-955b-ab2618bb8020",
                    "readOnly": True,
                    "eventType": "AwsApiCall",
                    "managementEvent": True,
                    "recipientAccountId": "111111111111",
                    "eventCategory": "Management",
                    "sessionCredentialFromConsole": "True",
                },
            ]
        }
    ),
    "AWSLogs/111111111111/CloudTrail/eu-west-2/2022/02/21/111111111111_CloudTrail_eu-west-2_20220221T1055Z_YhegGgxhib9WTAx8.json.gz": orjson.dumps(
        {
            "Records": [
                {
                    "eventVersion": "1.08",
                    "userIdentity": {
                        "type": "Root",
                        "principalId": "111111111111",
                        "arn": "arn:aws:iam::111111111111:root",
                        "accountId": "111111111111",
                        "accessKeyId": "ASIAUR6F6MOZQTDOKOWO",
                        "sessionContext": {
                            "sessionIssuer": {},
                            "webIdFederationData": {},
                            "attributes": {
                                "creationDate": "2022-02-21T09:06:22Z",
                                "mfaAuthenticated": "False",
                            },
                        },
                    },
                    "eventTime": "2022-02-21T10:11:12Z",
                    "eventSource": "ec2.amazonaws.com",
                    "eventName": "Create",
                    "awsRegion": "eu-west-2",
                    "sourceIPAddress": "78.197.123.35",
                    "userAgent": "EC2ConsoleFrontend, aws-internal/3 aws-sdk-java/1.12.150 Linux/5.4.172-100.336.amzn2int.x86_64 OpenJDK_64-Bit_Server_VM/25.322-b06 java/1.8.0_322 vendor/Oracle_Corporation cfg/retry-mode/standard",
                    "requestParameters": {
                        "availabilityZoneSet": {},
                        "availabilityZoneIdSet": {},
                    },
                    "responseElements": None,
                    "requestID": "9a038743-41e8-4c41-b76a-a34811370d39",
                    "eventID": "9eb7b17e-9434-434f-9cbc-9982be377594",
                    "readOnly": True,
                    "eventType": "AwsApiCall",
                    "managementEvent": True,
                    "recipientAccountId": "111111111111",
                    "eventCategory": "Management",
                    "sessionCredentialFromConsole": "True",
                },
                {
                    "eventVersion": "1.08",
                    "userIdentity": {
                        "type": "Root",
                        "principalId": "111111111111",
                        "arn": "arn:aws:iam::111111111111:root",
                        "accountId": "111111111111",
                        "accessKeyId": "ASIAUR6F6MOZQTDOKOWO",
                        "sessionContext": {
                            "sessionIssuer": {},
                            "webIdFederationData": {},
                            "attributes": {
                                "creationDate": "2022-02-21T09:06:22Z",
                                "mfaAuthenticated": "False",
                            },
                        },
                    },
                    "eventTime": "2022-02-21T10:11:12Z",
                    "eventSource": "s3.amazonaws.com",
                    "eventName": "Copy",
                    "awsRegion": "eu-west-2",
                    "sourceIPAddress": "78.197.123.35",
                    "userAgent": "EC2ConsoleFrontend, aws-internal/3 aws-sdk-java/1.12.150 Linux/5.4.172-100.336.amzn2int.x86_64 OpenJDK_64-Bit_Server_VM/25.322-b06 java/1.8.0_322 vendor/Oracle_Corporation cfg/retry-mode/standard",
                    "requestParameters": {
                        "maxResults": 1000,
                        "instancesSet": {},
                        "filterSet": {
                            "items": [
                                {
                                    "name": "instance-state-code",
                                    "valueSet": {"items": [{"value": "16"}]},
                                }
                            ]
                        },
                    },
                    "responseElements": None,
                    "requestID": "31cd443b-4ff7-458d-9f38-18fdf629373b",
                    "eventID": "e600c469-ca11-4d19-8151-a782ba8b95cd",
                    "readOnly": True,
                    "eventType": "AwsApiCall",
                    "managementEvent": True,
                    "recipientAccountId": "111111111111",
                    "eventCategory": "Management",
                    "sessionCredentialFromConsole": "True",
                },
                {
                    "eventVersion": "1.08",
                    "userIdentity": {
                        "type": "Root",
                        "principalId": "111111111111",
                        "arn": "arn:aws:iam::111111111111:root",
                        "accountId": "111111111111",
                        "accessKeyId": "ASIAUR6F6MOZQTDOKOWO",
                        "sessionContext": {
                            "sessionIssuer": {},
                            "webIdFederationData": {},
                            "attributes": {
                                "creationDate": "2022-02-21T09:06:22Z",
                                "mfaAuthenticated": "False",
                            },
                        },
                    },
                    "eventTime": "2022-02-21T10:11:12Z",
                    "eventSource": "s3.amazonaws.com",
                    "eventName": "GetObject",
                    "awsRegion": "eu-west-2",
                    "sourceIPAddress": "78.197.123.35",
                    "userAgent": "EC2ConsoleFrontend, aws-internal/3 aws-sdk-java/1.12.150 Linux/5.4.172-100.336.amzn2int.x86_64 OpenJDK_64-Bit_Server_VM/25.322-b06 java/1.8.0_322 vendor/Oracle_Corporation cfg/retry-mode/standard",
                    "requestParameters": {
                        "maxResults": 1000,
                        "snapshotSet": {},
                        "ownersSet": {"items": [{"owner": "111111111111"}]},
                        "sharedUsersSet": {},
                        "filterSet": {},
                    },
                    "responseElements": None,
                    "requestID": "0be99d8c-8155-4328-aebe-0a8ffbcb5e74",
                    "eventID": "e783e1c9-c9fc-4359-b6e1-0f5ad5620098",
                    "readOnly": True,
                    "eventType": "AwsApiCall",
                    "managementEvent": True,
                    "recipientAccountId": "111111111111",
                    "eventCategory": "Management",
                    "sessionCredentialFromConsole": "True",
                },
            ]
        }
    ),
}

# flake8: qa

S3Mock = s3_mock(S3Objects)


SQSMessages = [
    '{"Records":[{"eventVersion":"2.1","eventSource":"aws:s3","awsRegion":"eu-west-2","eventTime":"2022-06-27T16:17:56.712Z","eventName":"ObjectCreated:Put","userIdentity":{"principalId":"AWS:AROAJ6N5EQDKQTHMBI5GS:regionalDeliverySession"},"requestParameters":{"sourceIPAddress":"52.56.67.70"},"responseElements":{"x-amz-request-id":"D4M2F8DTSQVJRX7C","x-amz-id-2":"HFot7T6fvHiCaoyE2K/J/uRDPqoDlYOE8vBGZmc/I9Wc+U7RgOrA4qYLaxjbPEnCb1XW4MnrOQ8+AZoCeBJVR53QY1UEN4VT"},"s3":{"s3SchemaVersion":"1.0","configurationId":"FlowLogs","bucket":{"name":"aws-cloudtrail-111111111111-3abc4c4f","ownerIdentity":{"principalId":"A2ZXD4XGWPNOQ9"},"arn":"arn:aws:s3:::aws-cloudtrail-111111111111-3abc4c4f"},"object":{"key":"AWSLogs/111111111111/CloudTrail/eu-west-2/2022/02/21/111111111111_CloudTrail_eu-west-2_20220221T1020Z_nTGkKkyO0OcwEIvv.json.gz","size":9234,"eTag":"0cdef8885755dff42b6fbd91732ae506","sequencer":"0062B9D834A809629F"}}}]}',
    '{"Service":"Amazon S3","Event":"s3:TestEvent","Time":"2022-06-27T16:14:56.447Z","Bucket":"aws-cloudtrail-logs-111111111111-3abc4c4f","RequestId":"JGMN6V8XHKTYJS5J","HostId":"Ea/gza8Js+dQmg+1DUhIX46sdeYZMBEMJJ5Vo9pZlmh6giANwm2cELcoRcCcQdgfcZmtK81b+p4="}',
    '{"Records":[{"eventVersion":"2.1","eventSource":"aws:s3","awsRegion":"eu-west-2","eventTime":"2022-06-27T16:19:22.631Z","eventName":"ObjectCreated:Put","userIdentity":{"principalId":"AWS:AROAJ6N5EQDKQTHMBI5GS:regionalDeliverySession"},"requestParameters":{"sourceIPAddress":"34.195.91.227"},"responseElements":{"x-amz-request-id":"3579M4QA3X2863DM","x-amz-id-2":"mqqIkQwXY7tryvk5DNHgFtP459rD9pJcXlUDwDg6/BgYy1GpfVf97jSxXYu3FF4zqfQloVtmLuXYHNMupXHiYVxaKDpg32cS"},"s3":{"s3SchemaVersion":"1.0","configurationId":"FlowLogs","bucket":{"name":"aws-cloudtrail-111111111111-3abc4c4f","ownerIdentity":{"principalId":"A2ZXD4XGWPNOQ9"},"arn":"arn:aws:s3:::aws-cloudtrail-111111111111-3abc4c4f"},"object":{"key":"AWSLogs/111111111111/CloudTrail/eu-west-2/2022/02/21/111111111111_CloudTrail_eu-west-2_20220221T1055Z_YhegGgxhib9WTAx8.json.gz","size":1084,"eTag":"54a88e9fdedaeda828710cd3ad23a83c","sequencer":"0062B9D88A7DF00CB0"}}}]}',
]


SQSMock = sqs_mock(SQSMessages)


def test_get_next_objects(trigger, aws_mock):
    with mock.client.handler_for("s3", S3Mock), mock.client.handler_for("sqs", SQSMock):
        assert [obj.key for obj in trigger.get_next_objects(trigger.get_next_messages())] == list(S3Objects.keys())


def test_check_if_payload_is_valid(trigger):
    assert trigger.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "List"}) is False
    assert trigger.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "Describe"}) is False
    assert trigger.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "GetObjectTagging"}) is False
    assert trigger.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "Random"}) is False
    assert trigger.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "Delete"}) is True
    assert trigger.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "Create"}) is True
    assert trigger.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "Copy"}) is True
    assert trigger.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "Put"}) is True
    assert trigger.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "Restore"}) is True
    assert trigger.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "GetObject"}) is True
    assert trigger.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "GetObjectTorrent"}) is True
    assert trigger.is_valid_payload({"eventSource": "s3.amazonaws.com", "eventName": "ListBuckets"}) is True

    assert trigger.is_valid_payload({"eventSource": "random.amazonaws.com", "eventName": "List"}) is False
    assert trigger.is_valid_payload({"eventSource": "random.amazonaws.com", "eventName": "Describe"}) is False
    assert trigger.is_valid_payload({"eventSource": "random.amazonaws.com", "eventName": "Delete"}) is True
    assert trigger.is_valid_payload({"eventSource": "random.amazonaws.com", "eventName": "Create"}) is True
    assert trigger.is_valid_payload({"eventSource": "random.amazonaws.com", "eventName": "Random"}) is True


def test_forward_next_batches(trigger, aws_mock, symphony_storage):
    with mock.client.handler_for("s3", S3Mock), mock.client.handler_for("sqs", SQSMock):
        trigger.forward_next_batches()
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls) == 2
        assert [record for call in calls for record in call] == [
            orjson.dumps(record).decode("utf-8")
            for obj in S3Objects.values()
            for record in orjson.loads(obj)["Records"]
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
    "AWSLogs/111111111111/CloudTrail/eu-west-2/2022/02/21/111111111111_CloudTrail_eu-west-2_20220221T1020Z_nTGkKkyO0OcwEIvv.json.gz": b"{}",
    "AWSLogs/111111111111/CloudTrail/eu-west-2/2022/02/21/111111111111_CloudTrail_eu-west-2_20220221T1055Z_YhegGgxhib9WTAx8.json.gz": b"{}",
}

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
    trigger = AWSS3RecordsTrigger(module=module, data_path=symphony_storage)
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
