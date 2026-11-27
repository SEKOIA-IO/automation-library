from unittest.mock import Mock

import pytest

from office365.message_trace.client.retry import Retry


@pytest.mark.parametrize(
    "retry_after,expected",
    [
        pytest.param("120", 120, id="retry_after_header"),
        pytest.param(None, None, id="no_retry_after_header"),
        pytest.param("", None, id="empty_retry_after_header"),
    ],
)
def test_get_retry_after(retry_after, expected):
    response = Mock()
    response.getheader.return_value = retry_after

    assert Retry().get_retry_after(response) == expected
    response.getheader.assert_called_once_with("Retry-After")
