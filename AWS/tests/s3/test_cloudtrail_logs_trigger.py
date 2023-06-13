import os
from unittest.mock import Mock

import orjson
import pytest
from sekoia_automation.storage import PersistentJSON

from aws.base import AWSModule
from aws.s3.trigger_cloudtrail_logs import CloudTrailLogsTrigger, CloudTrailLogsWorker
from tests import mock
from tests.base import aws_regions, s3_mock
from tests.utils import read_file


@pytest.fixture
def trigger(symphony_storage):
    module = AWSModule()
    trigger = CloudTrailLogsTrigger(module=module, data_path=symphony_storage)
    trigger.module.configuration = {
        "aws_access_key": "access_key",
        "aws_secret_access_key": "secret_key",
        "aws_region_name": "eu-west-2",
    }
    trigger.configuration = {
        "frequency": 604800,
        "bucket_name": "aws-cloudtrail-logs-111111111111-3abc4c4f",
        "intake_key": "1234567890",
    }
    trigger.send_event = Mock()
    trigger.log = Mock()
    trigger.log_exception = Mock()
    yield trigger


@pytest.fixture
def prefix(trigger):
    return "AWSLogs/111111111111/CloudTrail/eu-west-2/"


@pytest.fixture
def worker(trigger, prefix):
    return CloudTrailLogsWorker(trigger, prefix, data_path=trigger._data_path)


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
                    "eventName": "DescribeAccountAttributes",
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
                    "eventName": "DescribeInstanceStatus",
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
                    "eventName": "DescribeAvailabilityZones",
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
                    "eventSource": "ec2.amazonaws.com",
                    "eventName": "DescribeInstances",
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
                    "eventSource": "ec2.amazonaws.com",
                    "eventName": "DescribeSnapshots",
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
        assert all([name.startswith("aws-cloudtrail_") for name in calls.keys()])
        assert [
            record
            for call in calls.values()
            for record in read_file(symphony_storage, call["directory"], call["event"]["records_path"])
        ] == [record for obj in S3Objects.values() for record in orjson.loads(obj)["Records"]]


def test_commit_marker(worker, prefix, aws_mock, symphony_storage):
    with mock.client.handler_for("s3", S3Mock):
        worker.forward_events()
        worker.commit_marker()
        context = PersistentJSON("context.json", data_path=symphony_storage.joinpath(prefix))
        with context as variables:
            assert variables.get("marker") == list(S3Objects.keys()).pop()


def test_read_marker(aws_mock, symphony_storage, prefix):
    worker_directory = symphony_storage.joinpath(prefix)
    if not worker_directory.exists():
        worker_directory.mkdir(parents=True, exist_ok=True)
    context = PersistentJSON("context.json", data_path=worker_directory)
    with context as variables:
        variables["marker"] = list(S3Objects.keys()).pop()

    with mock.client.handler_for("s3", S3Mock):
        module = AWSModule()
        trigger = CloudTrailLogsTrigger(module=module, data_path=symphony_storage)
        trigger.module.configuration = {
            "aws_access_key": "access_key",
            "aws_secret_access_key": "secret_key",
            "aws_region_name": "eu-west-2",
        }
        trigger.configuration = {
            "frequency": 604800,
            "bucket_name": "aws-cloudtrail-logs-111111111111-3abc4c4f",
            "intake_key": "1234567890",
        }
        trigger.send_event = Mock()
        trigger.log = Mock()
        trigger.log_exception = Mock()
        worker = CloudTrailLogsWorker(trigger, prefix)
        worker.forward_events()
        calls = {
            call.kwargs["event_name"]: call.kwargs.get("event")
            for call in trigger.send_event.call_args_list
            if call.kwargs.get("event_name")
        }
        assert len(calls) == 0


def test_get_last_key(worker, aws_mock, symphony_storage):
    with mock.client.handler_for("s3", S3Mock):
        last_key = worker.get_last_key(None)
        assert last_key == list(S3Objects.keys()).pop()


@pytest.mark.skipif(
    "{'AWS_API_KEY', 'AWS_API_SECRET_KEY', 'AWS_BUCKET_NAME', \
            'AWS_REGION'}.issubset(os.environ.keys()) == False"
)
def test_forward_events_integration(symphony_storage):
    module = AWSModule()
    trigger = CloudTrailLogsTrigger(module=module, data_path=symphony_storage)
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

    worker = CloudTrailLogsWorker(trigger, prefix)
    worker.forward_events()
    calls = {
        call.kwargs["event_name"]: call.kwargs
        for call in trigger.send_event.call_args_list
        if call.kwargs.get("event_name")
    }
    assert len(calls) > 0
    assert all([name.startswith("aws-cloudtrail_") for name in calls.keys()])
    assert all(
        isinstance(record, dict)
        for call in calls.values()
        for record in read_file(symphony_storage, call["directory"], call["event"]["records_path"])
    )
