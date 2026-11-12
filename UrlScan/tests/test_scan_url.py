import json

import httpx
import pytest
from httpx import Response

from tests.payloads import BASE, PNG, SCAN_ID, result_payload, submission_payload
from urlscan_modules.action.action_scan_url import ScanUrl

URL = "https://example.com"
HINT = 'retrieve it later with "Get scan result"'
BLACKLIST = {"message": "The submitted domain is on our blacklist, we will not scan it."}


@pytest.fixture
def action(module, tmp_path):
    return ScanUrl(module=module, data_path=tmp_path)


@pytest.fixture
def routes(api):
    return {
        "post": api.post("/api/v1/scan/").respond(200, json=submission_payload()),
        "head": api.head(f"/api/v1/result/{SCAN_ID}/").respond(200),
        "result": api.get(f"/api/v1/result/{SCAN_ID}/").respond(200, json=result_payload()),
        "screenshot": api.get(f"/screenshots/{SCAN_ID}.png").respond(200, content=PNG),
        "dom": api.get(f"/dom/{SCAN_ID}/").respond(200, text="<html>"),
    }


def body(route):
    return json.loads(route.calls.last.request.content)


def test_default_submission(action, routes):
    summary = action.run({"url": URL})

    assert body(routes["post"]) == {"url": URL, "visibility": "private"}
    assert summary is not None
    assert summary["status"] == "done"
    assert summary["uuid"] == SCAN_ID
    assert summary["comment"] is not None


def test_options_are_sent(action, routes):
    action.run({"url": URL, "customagent": "UA", "visibility": "unlisted", "tags": ["a", "b"], "country": " FR "})

    assert body(routes["post"]) == {
        "url": URL,
        "visibility": "unlisted",
        "tags": ["a", "b"],
        "customagent": "UA",
        "country": "fr",
    }


@pytest.mark.parametrize(
    "options",
    [
        {
            "customagent": None,
            "visibility": None,
            "tags": None,
            "country": None,
            "fail_on_blacklisted_url": None,
            "wait_for_result": None,
            "timeout": None,
        },
        {"customagent": "", "tags": [], "country": ""},
    ],
)
def test_empty_and_null_options_use_defaults(action, routes, options):
    summary = action.run({"url": URL} | options)

    assert body(routes["post"]) == {"url": URL, "visibility": "private"}
    assert summary is not None
    assert summary["status"] == "done"


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"url": None}, '"url" is required'),
        ({"url": " "}, '"url" is required'),
        ({"url": URL, "tags": [str(i) for i in range(11)]}, "At most 10 tags are allowed, got 11"),
        ({"url": URL, "country": "fra"}, '"country" must be a two-letter ISO 3166-1 alpha-2 code'),
        ({"url": URL, "country": "1a"}, '"country" must be a two-letter ISO 3166-1 alpha-2 code'),
        ({"url": URL, "timeout": 29}, '"timeout" must be between 30 and 600 seconds'),
        ({"url": URL, "timeout": 601}, '"timeout" must be between 30 and 600 seconds'),
        ({"url": URL, "visibility": "secret"}, '"visibility" must be one of public, unlisted, private'),
        (
            {"url": "http://10.0.0.1/"},
            "The URL host '10.0.0.1' is a private address and will not be sent to urlscan.io",
        ),
    ],
)
def test_invalid_arguments_make_no_request(action, api, arguments, message):
    assert action.run(arguments) is None
    assert action.error_message == message
    assert api.calls.call_count == 0


def test_no_wait_returns_submitted(action, api, routes):
    summary = action.run({"url": URL, "wait_for_result": False})

    assert summary is not None
    assert summary["status"] == "submitted"
    assert summary["report_url"] == f"{BASE}/result/{SCAN_ID}/"
    assert summary["comment"] is None
    assert api.calls.call_count == 1


def test_visibility_from_response(action, routes):
    routes["post"].respond(200, json=submission_payload(visibility="private"))

    result = action.run({"url": URL, "visibility": "public", "wait_for_result": False})

    assert result is not None
    assert result["visibility"] == "private"


def test_blacklisted_fails_by_default(action, routes):
    routes["post"].respond(400, json=BLACKLIST)

    assert action.run({"url": URL}) is None
    assert action.error_message == (
        "urlscan.io API error 400: The submitted domain is on our blacklist, we will not scan it."
    )


def test_blacklisted_status_when_allowed(action, routes):
    routes["post"].respond(400, json=BLACKLIST)

    summary = action.run({"url": URL, "fail_on_blacklisted_url": False})

    assert summary is not None
    assert summary["status"] == "blacklisted"
    assert summary["submitted_url"] == URL
    assert action.error_message is None


def test_other_refusal_fails(action, routes):
    routes["post"].respond(
        400,
        json={"message": "DNS Error - Could not resolve domain", "description": "The domain x could not be resolved"},
    )

    assert action.run({"url": URL, "fail_on_blacklisted_url": False}) is None
    assert action.error_message == (
        "urlscan.io API error 400: DNS Error - Could not resolve domain - The domain x could not be resolved"
    )


def test_submission_not_retried(action, routes):
    routes["post"].respond(502, json={"message": "Bad Gateway"})

    assert action.run({"url": URL}) is None
    assert routes["post"].call_count == 1
    assert action.error_message == "urlscan.io API error 502: Bad Gateway"


def test_submission_waits_on_rate_limit(action, routes):
    routes["post"].side_effect = [
        Response(429, json={"message": "Rate limit"}, headers={"X-Rate-Limit-Reset-After": "5"}),
        Response(200, json=submission_payload()),
    ]

    summary = action.run({"url": URL})

    assert routes["post"].call_count == 2
    assert summary is not None
    assert summary["status"] == "done"


def test_timeout_then_not_found(action, routes):
    routes["head"].respond(404)
    routes["result"].respond(404, json={"message": "No such scan submission"})

    assert action.run({"url": URL, "timeout": 30}) is None
    assert action.error_message == f"Scan {SCAN_ID} did not finish within 30 seconds; {HINT}"


def test_timeout_then_deleted(action, routes):
    routes["head"].respond(404)
    routes["result"].respond(410, json={"message": "Scan deleted"})

    assert action.run({"url": URL}) is None
    assert action.error_message == f"Scan {SCAN_ID} has been deleted"


def test_timeout_then_finished(action, routes):
    routes["head"].respond(404)

    summary = action.run({"url": URL})

    assert summary is not None
    assert summary["status"] == "done"


def test_polling_waits(action, routes, clock):
    routes["head"].side_effect = [Response(404), Response(404), Response(200)]
    start = clock[0]

    action.run({"url": URL})

    assert routes["head"].call_count == 3
    assert clock[0] - start == 14


def test_network_error_while_waiting(action, routes):
    routes["head"].side_effect = httpx.ConnectError("boom")

    summary = action.run({"url": URL})

    assert summary is not None
    assert summary["status"] == "done"


def test_network_error_then_not_found(action, routes):
    routes["head"].side_effect = httpx.ConnectError("boom")
    routes["result"].respond(404, json={"message": "No such scan submission"})

    assert action.run({"url": URL}) is None
    assert action.error_message == (
        f"Scan {SCAN_ID} was submitted but urlscan.io could not be reached while waiting; {HINT}"
    )


def test_result_error_after_submission(action, routes):
    routes["result"].respond(500, json={"message": "Internal Server Error"})

    assert action.run({"url": URL}) is None
    assert action.error_message == (
        f"Scan {SCAN_ID} was submitted but its result could not be retrieved "
        f"(urlscan.io API error 500: Internal Server Error); {HINT}"
    )


def test_unexpected_error_body_after_submission(action, routes):
    routes["result"].respond(500, json={})

    assert action.run({"url": URL}) is None
    assert action.error_message == (
        f"Scan {SCAN_ID} was submitted but its result could not be retrieved "
        f"(urlscan.io returned an unexpected error response); {HINT}"
    )


def test_unreachable_after_submission(action, routes):
    routes["result"].mock(side_effect=httpx.ConnectError("boom"))

    assert action.run({"url": URL}) is None
    assert action.error_message == (
        f"Scan {SCAN_ID} was submitted but its result could not be retrieved "
        f"(urlscan.io could not be reached: ConnectError); {HINT}"
    )
