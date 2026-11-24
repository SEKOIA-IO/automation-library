"""Classification of AWS errors."""

from botocore.exceptions import ClientError, EndpointConnectionError

# error codes that retrying can't fix: wrong credentials, missing permissions or wrong configuration
FATAL_ERROR_CODES = frozenset(
    {
        "AccessDenied",
        "AccountProblem",
        "AllAccessDisabled",
        "InvalidAccessKeyId",
        "InvalidObjectState",
        "InvalidPayer",
        "InvalidSecurity",
        "InvalidClientTokenId",
        "KMS.DisabledException",
        "MissingAuthenticationToken",
        "NotSignedUp",
        "QueueDoesNotExist",
        "RequestTimeTooSkewed",
        "SignatureDoesNotMatch",
        "UnauthorizedAccessError",
        "UnexpectedIPError",
    }
)


def is_fatal_error(error: Exception) -> bool:
    """Tell whether the error can't be fixed by retrying: the connector must stop."""
    if isinstance(error, ClientError):
        return error.response.get("Error", {}).get("Code") in FATAL_ERROR_CODES

    return isinstance(error, EndpointConnectionError)
