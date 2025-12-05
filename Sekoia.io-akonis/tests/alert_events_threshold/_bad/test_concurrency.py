import pytest
import asyncio
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_concurrent_notifications(trigger, monkeypatch):
    alert = {"uuid": "a1", "short_id": "A1", "events_count": 5,
             "rule": {"name": "R", "uuid": "u"}}

    trigger._retrieve_alert_from_alertapi = AsyncMock(return_value=alert)
    trigger._count_events_in_time_window = AsyncMock(return_value=1)
    trigger.state_manager.get_alert_state = lambda _: None

    send_event = AsyncMock()
    monkeypatch.setattr(trigger, "send_event", send_event)

    async def run_one():
        await trigger._process_alert_update({"alert_uuid": "a1"})

    await asyncio.gather(
        run_one(),
        run_one(),
        run_one(),
    )

    # Should trigger 3 independent events
    assert send_event.await_count == 3
