import pytest
import json
import asyncio

@pytest.mark.asyncio
async def test_retry_logic_success_on_second_attempt(trigger, monkeypatch, aresponses):

    # Avoid actual sleeps
    monkeypatch.setattr(asyncio, "sleep", lambda *_: asyncio.sleep(0))

    # 1st call: network error
    aresponses.add(
        "mockserver",
        "/alert/a1",
        "get",
        aresponses.Response(status=503, text="temporary error"),
    )

    # 2nd call: success
    aresponses.add(
        "mockserver",
        "/alert/a1",
        "get",
        aresponses.Response(
            status=200,
            text=json.dumps({"uuid": "a1"}),
            headers={"Content-Type": "application/json"}
        ),
    )

    data = await trigger._retrieve_alert_from_alertapi("a1")
    assert data["uuid"] == "a1"
