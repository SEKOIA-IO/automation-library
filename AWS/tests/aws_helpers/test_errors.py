"""Test AWS errors classification."""

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from aws_helpers.errors import is_fatal_error


@pytest.mark.parametrize(
    "error, expected",
    [
        (ClientError({"Error": {"Code": "InvalidClientTokenId"}}, "ReceiveMessage"), True),
        (ClientError({"Error": {"Code": "AccessDenied"}}, "GetObject"), True),
        (ClientError({"Error": {"Code": "KMS.DisabledException"}}, "GetObject"), True),
        (ClientError({"Error": {"Code": "QueueDoesNotExist"}}, "ReceiveMessage"), True),
        (ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject"), False),
        (EndpointConnectionError(endpoint_url="https://sqs.test.amazonaws.com/"), True),
        (ClientError({"Error": {"Code": "Throttling"}}, "ReceiveMessage"), False),
        (ValueError("boom"), False),
    ],
)
def test_is_fatal_error(error: Exception, expected: bool):
    assert is_fatal_error(error) is expected
