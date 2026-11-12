import pytest
from httpx import Response

from tests.payloads import BASE, PNG, SCAN_ID, result_payload
from urlscan_modules.action.action_get_scan_result import GetScanResult

START = 1_800_000_000.0


@pytest.fixture
def action(module, tmp_path):
    return GetScanResult(module=module, data_path=tmp_path)


@pytest.fixture
def routes(api):
    return {
        "result": api.get(f"/api/v1/result/{SCAN_ID}/").respond(200, json=result_payload()),
        "screenshot": api.get(f"/screenshots/{SCAN_ID}.png").respond(200, content=PNG),
        "dom": api.get(f"/dom/{SCAN_ID}/").respond(200, text="<html>"),
    }


def test_returns_summary_with_comment(action, routes):
    summary = action.run({"scan_id": SCAN_ID})

    assert summary is not None
    assert summary["status"] == "done"
    assert summary["screenshot_available"] is True
    assert summary["dom_available"] is True
    assert summary["comment"].startswith("**urlscan.io scan** of")
    assert action.error_message is None
    assert routes["result"].call_count == 1


def test_screenshot_not_stored(action, routes):
    routes["screenshot"].respond(404, content=PNG)

    summary = action.run({"scan_id": SCAN_ID})

    assert summary["screenshot_available"] is False
    assert summary["screenshot_url"] is None
    assert "Screenshot: not stored by urlscan.io" in summary["comment"]
    assert not any("PNG" in entry["message"] for entry in action.logs)


def test_dom_not_stored(action, routes):
    routes["dom"].respond(404)

    summary = action.run({"scan_id": SCAN_ID})

    assert summary["dom_available"] is False
    assert summary["dom_url"] is None


def test_availability_unknown(action, routes):
    routes["screenshot"].respond(500)

    summary = action.run({"scan_id": SCAN_ID})

    assert summary["screenshot_available"] is None
    assert summary["screenshot_url"] == f"{BASE}/screenshots/{SCAN_ID}.png"
    assert routes["screenshot"].call_count == 1
    warnings = [entry["message"] for entry in action.logs if entry["level"] == "warning"]
    assert warnings == [f"Could not check the screenshot of scan {SCAN_ID} (status 500)"]


def test_availability_unknown_on_unexpected_error_body(action, routes):
    routes["screenshot"].respond(500, json={})

    summary = action.run({"scan_id": SCAN_ID})

    assert summary["screenshot_available"] is None
    assert summary["screenshot_url"] == f"{BASE}/screenshots/{SCAN_ID}.png"
    assert action.error_message is None


def test_missing_lists_refetched(action, routes, clock):
    incomplete = {key: value for key, value in result_payload().items() if key != "lists"}
    routes["result"].side_effect = [
        Response(200, json=incomplete),
        Response(200, json=incomplete),
        Response(200, json=result_payload()),
    ]

    summary = action.run({"scan_id": SCAN_ID})

    assert routes["result"].call_count == 3
    assert clock[0] - START == 10
    assert summary["contacted"]["domains"] == ["example.com"]


def test_missing_lists_gives_up(action, routes):
    incomplete = {key: value for key, value in result_payload().items() if key != "lists"}
    routes["result"].respond(200, json=incomplete)

    summary = action.run({"scan_id": SCAN_ID})

    assert routes["result"].call_count == 4
    assert summary["contacted"]["domains"] == []


def test_not_found(action, routes):
    routes["result"].respond(404, json={"message": "No such scan submission"})

    assert action.run({"scan_id": SCAN_ID}) is None
    assert action.error_message == f"Scan {SCAN_ID} not found or not finished yet"


def test_deleted(action, routes):
    routes["result"].respond(410, json={"message": "Scan deleted"})

    assert action.run({"scan_id": SCAN_ID}) is None
    assert action.error_message == f"Scan {SCAN_ID} has been deleted"


def test_other_api_error(action, routes):
    routes["result"].respond(403, json={"message": "Forbidden"})

    assert action.run({"scan_id": SCAN_ID}) is None
    assert action.error_message == "urlscan.io API error 403: Forbidden"


def test_invalid_scan_id(action, api):
    assert action.run({"scan_id": "../x"}) is None
    assert action.error_message == "'../x' is not a valid scan UUID"
    assert api.calls.call_count == 0
