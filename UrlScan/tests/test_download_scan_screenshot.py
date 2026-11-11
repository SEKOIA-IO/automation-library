import pytest

from tests.payloads import BASE, PNG, SCAN_ID
from urlscan_modules.download_scan_screenshot import DownloadScanScreenshot


@pytest.fixture
def action(module, tmp_path):
    return DownloadScanScreenshot(module=module, data_path=tmp_path)


@pytest.fixture
def route(api):
    return api.get(f"/screenshots/{SCAN_ID}.png")


def test_writes_png(action, route, tmp_path):
    route.respond(200, content=PNG)

    result = action.run({"scan_id": SCAN_ID})

    assert result == {
        "screenshot_path": f"urlscan/{SCAN_ID}.png",
        "screenshot_url": f"{BASE}/screenshots/{SCAN_ID}.png",
        "size": len(PNG),
    }
    assert (tmp_path / "urlscan" / f"{SCAN_ID}.png").read_bytes() == PNG


def test_not_stored(action, route, tmp_path):
    route.respond(404, content=PNG)

    assert action.run({"scan_id": SCAN_ID}) is None

    assert action.error_message == (
        f"Screenshot of scan {SCAN_ID} was not stored by urlscan.io (or the scan is unknown or not finished)"
    )
    assert list(tmp_path.iterdir()) == []
    assert not any("PNG" in entry["message"] for entry in action.logs)


def test_invalid_body(action, route, tmp_path):
    route.respond(200, content=b"<html>")

    assert action.run({"scan_id": SCAN_ID}) is None

    assert action.error_message == f"urlscan.io returned an invalid screenshot for scan {SCAN_ID}"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("scan_id", ["../../x", f"{BASE}/result/{SCAN_ID}/"])
def test_invalid_scan_id(action, api, tmp_path, scan_id):
    assert action.run({"scan_id": scan_id}) is None

    assert action.error_message.endswith("is not a valid scan UUID")
    assert api.calls.call_count == 0
    assert list(tmp_path.iterdir()) == []


def test_server_error(action, route):
    route.respond(500, json={"message": "Internal Server Error"})

    assert action.run({"scan_id": SCAN_ID}) is None

    assert action.error_message == "urlscan.io API error 500: Internal Server Error"
    assert route.call_count == 4
