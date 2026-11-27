"""Classification of AWS errors."""

from collections.abc import Iterator

from botocore.exceptions import ClientError, EndpointConnectionError

# error codes that retrying can't fix: wrong credentials, missing permissions or wrong configuration
FATAL_ERROR_CODES = frozenset(
    {
        "AccessDenied",
        "AccountProblem",
        "AllAccessDisabled",
        "InvalidAccessKeyId",
        "InvalidPayer",
        "InvalidSecurity",
        "InvalidClientTokenId",
        "KMS.DisabledException",
        "MissingAuthenticationToken",
        "NoSuchBucket",
        "NotSignedUp",
        # SQS speaks the query protocol: botocore reports this one under its legacy name
        "AWS.SimpleQueueService.NonExistentQueue",
        "QueueDoesNotExist",
        "SignatureDoesNotMatch",
        "UnauthorizedAccessError",
        "UnexpectedIPError",
    }
)


def _causes(error: BaseException | None) -> Iterator[BaseException]:
    """Yield the error and its causes: AWS errors are often wrapped, e.g. by the OIDC role assumption."""
    seen: set[int] = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        yield error
        error = error.__cause__


def is_endpoint_error(error: BaseException) -> bool:
    """Tell whether the AWS endpoint can't be reached: a wrong endpoint, but also a network outage."""
    return any(isinstance(cause, EndpointConnectionError) for cause in _causes(error))


def is_fatal_error(error: BaseException) -> bool:
    """Tell whether the error can't be fixed by retrying: the connector must stop."""
    if is_endpoint_error(error):
        return True

    for cause in _causes(error):
        if isinstance(cause, ClientError):
            response = cause.response.get("Error", {})
            if FATAL_ERROR_CODES & {response.get("Code"), response.get("QueryErrorCode")}:
                return True

    return False
