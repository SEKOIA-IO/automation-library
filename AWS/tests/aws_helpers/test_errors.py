"""Test AWS errors classification."""

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from aws_helpers.errors import is_endpoint_error, is_fatal_error


def _client_error(code: str, **extra: str) -> ClientError:
    return ClientError({"Error": {"Code": code, **extra}}, "GetObject")


def _wrapped(error: Exception) -> RuntimeError:
    try:
        raise RuntimeError("Could not assume role") from error
    except RuntimeError as wrapper:
        return wrapper


@pytest.mark.parametrize(
    "error, expected",
    [
        (_client_error("InvalidClientTokenId"), True),
        (_client_error("AccessDenied"), True),
        (_client_error("KMS.DisabledException"), True),
        (_client_error("NoSuchBucket"), True),
        (_client_error("QueueDoesNotExist"), True),
        # SQS reports the legacy code, and the modelled one separately
        (_client_error("AWS.SimpleQueueService.NonExistentQueue"), True),
        (_client_error("Other", QueryErrorCode="QueueDoesNotExist"), True),
        # errors about one object or temporary conditions
        (_client_error("NoSuchKey"), False),
        (_client_error("InvalidObjectState"), False),
        (_client_error("RequestTimeTooSkewed"), False),
        (_client_error("Throttling"), False),
        (EndpointConnectionError(endpoint_url="https://sqs.test.amazonaws.com/"), True),
        (_wrapped(_client_error("AccessDenied")), True),
        (_wrapped(EndpointConnectionError(endpoint_url="https://sqs.test.amazonaws.com/")), True),
        (_wrapped(ValueError("boom")), False),
        (ValueError("boom"), False),
    ],
)
def test_is_fatal_error(error: Exception, expected: bool):
    assert is_fatal_error(error) is expected


def test_is_endpoint_error():
    endpoint_error = EndpointConnectionError(endpoint_url="https://sqs.test.amazonaws.com/")

    assert is_endpoint_error(endpoint_error)
    assert is_endpoint_error(_wrapped(endpoint_error))
    assert not is_endpoint_error(_client_error("AccessDenied"))
