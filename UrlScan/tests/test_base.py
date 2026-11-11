import logging
from unittest.mock import Mock

import httpx
import pytest
from urlscan import APIError, RateLimitError
from urlscan.error import RateLimitRemainingError

from urlscan_modules.base import ActionError, UrlScanAction, describe_error

START = 1_800_000_000.0


class Probe(UrlScanAction):
    def perform(self, client, arguments):
        if "raise" in arguments:
            raise arguments["raise"]
        return {"quotas": self.call(client.get_quotas)}


@pytest.fixture
def action(module, tmp_path):
    return Probe(module=module, data_path=tmp_path)


def rate_limited(seconds: int | None = None) -> httpx.Response:
    headers = {} if seconds is None else {"X-Rate-Limit-Reset-After": str(seconds)}
    return httpx.Response(429, json={"message": "Rate limit"}, headers=headers)


def test_client_sends_api_key(action, api):
    route = api.get("/api/v1/quotas").respond(200, json={"scope": "team"})

    assert action.run({}) == {"quotas": {"scope": "team"}}
    assert route.calls.last.request.headers["API-Key"] == "test-api-key"
    assert action.error_message is None


def test_server_error_retried(action, api, clock):
    route = api.get("/api/v1/quotas")
    route.side_effect = [httpx.Response(502), httpx.Response(502), httpx.Response(502), httpx.Response(200, json={})]

    assert action.run({}) == {"quotas": {}}
    assert route.call_count == 4
    assert clock[0] - START == 14


def test_server_error_exhausted(action, api):
    route = api.get("/api/v1/quotas").respond(503, json={"message": "Service Unavailable"})

    assert action.run({}) is None
    assert action.error_message == "urlscan.io API error 503: Service Unavailable"
    assert route.call_count == 4


def test_transport_error_retried(action, api):
    route = api.get("/api/v1/quotas")
    route.side_effect = httpx.ConnectError("boom")

    assert action.run({}) is None
    assert action.error_message == "urlscan.io could not be reached: ConnectError"
    assert route.call_count == 4


def test_rate_limit_waits(action, api, clock):
    route = api.get("/api/v1/quotas")
    route.side_effect = [rate_limited(30), httpx.Response(200, json={})]

    assert action.run({}) == {"quotas": {}}
    assert clock[0] - START == 31
    assert route.call_count == 2


def test_rate_limit_too_long(action, api, clock):
    route = api.get("/api/v1/quotas").mock(return_value=rate_limited(61))

    assert action.run({}) is None
    assert action.error_message == "urlscan.io quota exceeded for this action, retry after 61 seconds"
    assert route.call_count == 1
    assert clock[0] == START


def test_rate_limit_gives_up(action, api, clock):
    route = api.get("/api/v1/quotas").mock(return_value=rate_limited())

    assert action.run({}) is None
    assert route.call_count == 4
    assert clock[0] - START == 3
    assert action.error_message == "urlscan.io quota exceeded for this action, retry after 0 seconds"


def test_invalid_api_key(action, api):
    route = api.get("/api/v1/quotas").respond(401, json={"message": "API key supplied but not found in database!"})

    assert action.run({}) is None
    assert action.error_message == "Invalid urlscan.io API key"
    assert route.call_count == 1


def test_message_truncated(action, api):
    api.get("/api/v1/quotas").respond(
        400, json={"message": "DNS Error - Could not resolve domain", "description": "x" * 600}
    )

    assert action.run({}) is None
    assert action.error_message.startswith("urlscan.io API error 400: DNS Error - Could not resolve domain - xxx")
    assert len(action.error_message) == 500


def test_sdk_precheck_after_wait(action, clock):
    fn = Mock(
        side_effect=[
            RateLimitError("Rate limit", status=429, rate_limit_reset_after=5),
            RateLimitRemainingError("retrieve"),
            {"ok": True},
        ]
    )

    assert action.call(fn) == {"ok": True}
    assert clock[0] - START == 8
    assert fn.call_count == 3


def test_sdk_precheck_without_wait(action):
    fn = Mock(side_effect=[RateLimitRemainingError("search")])

    with pytest.raises(RateLimitRemainingError):
        action.call(fn)
    assert fn.call_count == 1


def test_server_and_rate_limit_combine(action, clock):
    fn = Mock(
        side_effect=[
            APIError("Bad Gateway", status=502),
            RateLimitError("Rate limit", status=429, rate_limit_reset_after=5),
            APIError("Bad Gateway", status=502),
            {"ok": True},
        ]
    )

    assert action.call(fn) == {"ok": True}
    assert clock[0] - START == 10
    assert fn.call_count == 4


def test_no_retry_when_disabled(action):
    fn = Mock(side_effect=[APIError("Bad Gateway", status=502)])

    with pytest.raises(APIError):
        action.call(fn, retry_server_errors=False)
    assert fn.call_count == 1


def test_error_body_without_message(action):
    fn = Mock(side_effect=KeyError("message"))

    with pytest.raises(ActionError, match=r"urlscan\.io returned an unexpected error response"):
        action.call(fn)


def test_rate_limit_remaining(action):
    assert action.run({"raise": RateLimitRemainingError("search")}) is None
    assert action.error_message == "urlscan.io quota exceeded for this action, retry later"


def test_action_error(action):
    assert action.run({"raise": ActionError("nope")}) is None
    assert action.error_message == "nope"


def test_unexpected_exception_propagates(action):
    with pytest.raises(RuntimeError):
        action.run({"raise": RuntimeError("bug")})


def test_unknown_error_description():
    assert describe_error(ValueError("x")) == "urlscan.io error: ValueError"


def test_httpx_request_logs_are_silenced():
    assert logging.getLogger("httpx").level == logging.WARNING
