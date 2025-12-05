import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_trigger_happy_path(trigger, monkeypatch):
    alert = {"uuid": "a1", "short_id": "A1", "events_count": 10,
             "rule": {"name": "OK", "uuid": "ru"}}

    trigger._retrieve_alert_from_alertapi = AsyncMock(return_value=alert)
    trigger._count_events_in_time_window = AsyncMock(return_value=1)
    trigger.state_manager.get_alert_state = lambda _: None

    send_event = AsyncMock()
    monkeypatch.setattr(trigger, "send_event", send_event)

    await trigger._process_alert_update({"alert_uuid": "a1"})

    send_event.assert_awaited_once()
