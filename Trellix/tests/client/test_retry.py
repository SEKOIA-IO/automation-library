from unittest.mock import MagicMock

from client.retry import RetryWithRateLimiter


def test_retry_with_success_request_should_call_underlying_retry_options():
    retry_options = MagicMock()
    response = MagicMock()
    response.status = 200
    retry = RetryWithRateLimiter(retry_options=retry_options)

    retry.get_timeout(1, response)
    assert retry_options.get_timeout.called


def test_retry_none_response_should_call_underlying_retry_options():
    retry_options = MagicMock()
    response = None
    retry = RetryWithRateLimiter(retry_options=retry_options)

    retry.get_timeout(1, response)
    assert retry_options.get_timeout.called


def test_retry_without_retry_after_should_call_underlying_retry_options():
    retry_options = MagicMock()
    response = MagicMock()
    response.status = 429
    response.headers = {}
    retry = RetryWithRateLimiter(retry_options=retry_options)

    retry.get_timeout(1, response)
    assert retry_options.get_timeout.called


def test_retry_with_exhausted_limit_should_wait_retry_after():
    retry_options = MagicMock()
    response = MagicMock()
    response.status = 429
    response.headers = {"Retry-After": 250}
    retry = RetryWithRateLimiter(retry_options=retry_options)

    time_to_sleep = retry.get_timeout(1, response)
    assert not retry_options.get_timeout.called
    assert time_to_sleep == 250
