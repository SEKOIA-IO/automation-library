import pytest
import json
from datetime import datetime, timedelta, timezone

@pytest.mark.asyncio
async def test_event_count_success(trigger, aresponses):

    aresponses.add(
        "mockserver",
        "/event/search",
        "post",
        aresponses.Response(
            status=200,
            text=json.dumps({"total": 42}),
            headers={"Content-Type": "application/json"}
        ),
    )

    count = await trigger._count_events_in_time_window("a1", 1)
    assert count == 42


@pytest.mark.asyncio
async def test_event_count_error_returns_zero(trigger, aresponses):

    aresponses.add(
        "mockserver",
        "/event/search",
        "post",
        aresponses.Response(
            status=500,
            text="internal error"
        ),
    )

    count = await trigger._count_events_in_time_window("a1", 1)
    assert count == 0
