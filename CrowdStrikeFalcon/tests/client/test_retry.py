import time
from unittest.mock import patch

from urllib3.response import HTTPResponse

from crowdstrike_falcon.client.retry import Retry


def test_retry_after_header_sleep():
    retry = Retry()

    with patch("time.sleep") as sleep_mock:
        # for the default behavior, it must be in RETRY_AFTER_STATUS_CODES
        response = HTTPResponse(status=503, headers={"Retry-After": "3600"})

        retry.sleep(response)

        sleep_mock.assert_called_with(3600)


def test_ratelimit_retry_after_header_sleep():
    retry = Retry()

    fixed_timestamp = 1664389951
    with patch("time.sleep") as sleep_mock, patch("time.time", return_value=fixed_timestamp):
        # for the default behavior, it must be in RETRY_AFTER_STATUS_CODES
        retry_timestamp = time.time() + 3600
        response = HTTPResponse(status=503, headers={"X-RateLimit-RetryAfter": str(retry_timestamp)})

        retry.sleep(response)

        sleep_mock.assert_called_with(3600)


def test_ratelimit_retry_after_in_the_past_returns_none():
    retry = Retry()

    with patch("time.time", return_value=1664389951):
        response = HTTPResponse(status=429, headers={"X-RateLimit-RetryAfter": "1664389000"})

        assert retry.get_retry_after(response) is None


def test_get_retry_after_without_headers_returns_none():
    retry = Retry()

    assert retry.get_retry_after(HTTPResponse(status=429, headers={})) is None
