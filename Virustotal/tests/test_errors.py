import pytest

from virustotal.errors import DuplicateCommentError, Error, MaxFileSizeExceedError, RequestLimitError


@pytest.mark.parametrize(
    "error_class,default_message",
    [
        (MaxFileSizeExceedError, "The file exceeds the maximum size of 200MB"),
        (RequestLimitError, "Request rate limit exceeded."),
        (DuplicateCommentError, "Duplicate comment"),
    ],
)
def test_error_default_message(error_class, default_message):
    error = error_class()

    assert isinstance(error, Error)
    assert error.message.startswith(default_message)
    assert str(error) == f"{error_class.__name__} {error.message}"


@pytest.mark.parametrize("error_class", [MaxFileSizeExceedError, RequestLimitError, DuplicateCommentError])
def test_error_custom_message(error_class):
    error = error_class(msg="custom message")

    assert error.message == "custom message"
    assert str(error) == f"{error_class.__name__} custom message"
