import time
from unittest.mock import MagicMock

import pytest

from aws.event_aggregator import EventAggregator, Fingerprint


@pytest.fixture
def decrypt_event():
    return {
        "message": "...",
        "cloud": {
            "provider": "aws",
            "service": {"name": "cloudtrail"},
            "region": "eu-west-1",
            "account": {"id": "000000000000"},
        },
        "@timestamp": "2023-10-27T19:00:00.000Z",
        "sekoiaio": {
            "indexation_time": "2023-10-28T01:44:53.657715537Z",
            "intake": {
                "parsing_status": "success",
                "dialect": "aws cloudtrail",
                "name": "cloudtrail",
                "dialect_uuid": "d3a813ac-f9b5-451c-a602-a5994544d9ed",
                "uuid": "e7e751d1-098e-4241-8a33-53fd92c45618",
                "key": "0000000000000000000000000",
                "parsing_duration_ms": 0.8749961853027344,
            },
        },
        "action": {
            "name": "Decrypt",
            "type": "AwsApiCall",
            "outcome": "success",
            "properties": {
                "recipientAccountId": "00000000000000",
                "resources": [
                    {
                        "accountId": "00000000000000",
                        "type": "AWS::KMS::Key",
                        "ARN": "arn:aws:kms:eu-west-1:000000000000:key/00000000-2d9d-4070-b5a8-5535f987ef07",
                    }
                ],
                "userIdentity": {
                    "accessKeyId": "222222222222222222222",
                    "sessionContext": {
                        "webIdFederationData": {},
                        "sessionIssuer": {
                            "accountId": "00000000000000",
                            "principalId": "1111111111111111111111",
                            "userName": "AmazonSageMaker-ExecutionRole-20191217T000000",
                            "type": "Role",
                            "arn": "arn:aws:iam::000000000000:role/service-role/AmazonSageMaker-ExecutionRole-20191217T000000",
                        },
                        "attributes": {"mfaAuthenticated": "false", "creationDate": "2023-10-27T18:51:44Z"},
                    },
                    "accountId": "000000000000",
                    "principalId": "1111111111111111111111:SageMaker",
                    "invokedBy": "AWS Internal",
                    "arn": "arn:aws:sts::000000000000:assumed-role/AmazonSageMaker-ExecutionRole-20191217T000000/SageMaker",
                    "type": "AssumedRole",
                },
            },
            "target": "network-traffic",
        },
        "aws": {
            "cloudtrail": {
                "flattened": {
                    "request_parameters": "",
                },
                "event_version": "1.08",
                "userIdentity": {
                    "accessKeyId": "222222222222222222222",
                    "sessionContext": {
                        "webIdFederationData": {},
                        "sessionIssuer": {
                            "accountId": "00000000000000",
                            "principalId": "1111111111111111111111",
                            "userName": "AmazonSageMaker-ExecutionRole-20191217T000000",
                            "type": "Role",
                            "arn": "arn:aws:iam::000000000000:role/service-role/AmazonSageMaker-ExecutionRole-20191217T000000",
                        },
                        "attributes": {"mfaAuthenticated": "false", "creationDate": "2023-10-27T18:51:44Z"},
                    },
                    "accountId": "000000000000",
                    "principalId": "1111111111111111111111:SageMaker",
                    "invokedBy": "AWS Internal",
                    "arn": "arn:aws:sts::000000000000:assumed-role/AmazonSageMaker-ExecutionRole-20191217T000000/SageMaker",
                    "type": "AssumedRole",
                },
                "resources": [
                    {
                        "accountId": "00000000000000000",
                        "type": "AWS::KMS::Key",
                        "ARN": "arn:aws:kms:eu-west-1:000000000000:key/00000000-2d9d-4070-b5a8-5535f987ef07",
                    }
                ],
                "recipient_account_id": "000000000000000",
            }
        },
        "event": {
            "dialect": "aws cloudtrail",
            "provider": "kms.amazonaws.com",
            "kind": "event",
            "created": "2023-10-28T01:44:50.159559+00:00",
            "action": "Decrypt",
            "id": "dd1d66a4-6890-4544-a3a1-95825331da01",
            "category": ["network"],
            "dialect_uuid": "d3a813ac-f9b5-451c-a602-a5994544d9ed",
            "type": ["access"],
            "dataset": "cloudtrail",
            "outcome": "success",
        },
    }


@pytest.fixture
def decrypt_event_aggregations():
    return {
        "d3a813ac-f9b5-451c-a602-a5994544d9ed": [
            Fingerprint(
                condition_func=lambda e: (e["event"]["action"] == "Decrypt"),
                build_hash_str_func=lambda e: f"{e['aws']['cloudtrail']['userIdentity']['arn']}:{e['aws']['cloudtrail']['resources'][0]['ARN']}",
                ttl=30,
            )
        ]
    }


def test_aggregation_twice(decrypt_event, decrypt_event_aggregations):
    aggregator = EventAggregator(aggregation_definitions=decrypt_event_aggregations)
    assert aggregator.aggregate(decrypt_event) == decrypt_event
    assert len(aggregator.aggregations) == 1

    assert aggregator.aggregate(decrypt_event) is None
    assert (
        aggregator.aggregations[
            (
                "d3a813ac-f9b5-451c-a602-a5994544d9ed;"
                "arn:aws:sts::000000000000:assumed-role/AmazonSageMaker-ExecutionRole-20191217T000000/SageMaker:"
                "arn:aws:kms:eu-west-1:000000000000:key/00000000-2d9d-4070-b5a8-5535f987ef07"
            )
        ].count
        == 1
    )


def test_fingerprint_condition_return_false(decrypt_event):
    aggregation_definitions = {
        "d3a813ac-f9b5-451c-a602-a5994544d9ed": [
            Fingerprint(
                condition_func=lambda e: (e["event"]["action"] == "Invalid"),
                build_hash_str_func=lambda e: f"{e['aws']['cloudtrail']['userIdentity']['arn']}:{e['aws']['cloudtrail']['resources'][0]['ARN']}",
                ttl=30,
            )
        ]
    }

    aggregator = EventAggregator(aggregation_definitions=aggregation_definitions)
    assert aggregator.aggregate(decrypt_event) == decrypt_event
    assert len(aggregator.aggregations) == 0


def test_fingerprint_condition_raises_error(decrypt_event):
    aggregation_definitions = {
        "d3a813ac-f9b5-451c-a602-a5994544d9ed": [
            Fingerprint(
                condition_func=lambda e: (e["unknown-field"] == "Invalid"),
                build_hash_str_func=lambda e: f"{e['aws']['cloudtrail']['userIdentity']['arn']}:{e['aws']['cloudtrail']['resources'][0]['ARN']}",
                ttl=30,
            )
        ]
    }

    aggregator = EventAggregator(aggregation_definitions=aggregation_definitions)
    assert aggregator.aggregate(decrypt_event) == decrypt_event
    assert len(aggregator.aggregations) == 0


def test_support_erroneous_events():
    aggregator = EventAggregator(aggregation_definitions={})
    assert aggregator.aggregate({}) == {}
    assert len(aggregator.aggregations) == 0


def test_flush_on_ttl(decrypt_event):
    aggregation_definitions = {
        "d3a813ac-f9b5-451c-a602-a5994544d9ed": [
            Fingerprint(
                condition_func=lambda e: (e["event"]["action"] == "Decrypt"),
                build_hash_str_func=lambda e: f"{e['aws']['cloudtrail']['userIdentity']['arn']}:{e['aws']['cloudtrail']['resources'][0]['ARN']}",
                ttl=2,
            )
        ]
    }
    magic = MagicMock()
    aggregator = EventAggregator(aggregation_definitions=aggregation_definitions)
    aggregator.start_flush_on_ttl(on_flush_func=magic, delay=0.5)
    aggregator.aggregate(decrypt_event)
    aggregator.aggregate(decrypt_event)
    time.sleep(2)
    aggregator.stop()
    assert magic.called


def test_flush_on_ttl_support_per_fingerprint_ttl(decrypt_event):
    aggregation_definitions = {
        "d3a813ac-f9b5-451c-a602-a5994544d9ed": [
            Fingerprint(
                condition_func=lambda e: (e["event"]["action"] == "Decrypt"),
                build_hash_str_func=lambda e: f"{e['aws']['cloudtrail']['userIdentity']['arn']}:{e['aws']['cloudtrail']['resources'][0]['ARN']}",
                ttl=2,
            )
        ]
    }
    magic = MagicMock()
    aggregator = EventAggregator(aggregation_definitions=aggregation_definitions)
    aggregator.start_flush_on_ttl(on_flush_func=magic, delay=0.5)
    aggregator.aggregate(decrypt_event)
    aggregator.aggregate(decrypt_event)
    time.sleep(2)
    aggregator.stop()
    assert magic.called


def test_flush_on_stop(decrypt_event):
    aggregation_definitions = {
        "d3a813ac-f9b5-451c-a602-a5994544d9ed": [
            Fingerprint(
                condition_func=lambda e: (e["event"]["action"] == "Decrypt"),
                build_hash_str_func=lambda e: f"{e['aws']['cloudtrail']['userIdentity']['arn']}:{e['aws']['cloudtrail']['resources'][0]['ARN']}",
                ttl=100,
            )
        ]
    }
    magic = MagicMock()
    aggregator = EventAggregator(aggregation_definitions=aggregation_definitions)
    aggregator.start_flush_on_ttl(on_flush_func=magic, delay=0.5)
    aggregator.aggregate(decrypt_event)
    aggregator.aggregate(decrypt_event)
    aggregator.aggregate(decrypt_event)
    aggregator.stop()
    assert magic.called
    assert magic.call_args_list[0].args[0]["sekoiaio"]["repeat"]["count"] == 2
