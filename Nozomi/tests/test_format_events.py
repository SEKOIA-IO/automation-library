import pytest
from nozomi_networks.nozomi_vantage_connector import _format_event


@pytest.mark.asyncio
async def test_alert_formatting():
    raw_alert = alert_record = {
        "id": "111111-111111-11111111",
        "type": "alerts",
        "attributes": {
            "ack": False,
        },
        "meta": {
            "other_field": 123
        }
    }


    result = _format_event(raw_alert)

    expected = {
        "id": "111111-111111-11111111",
        "event_type": "alerts",
        "ack": False,
        "meta": {
            "other_field": 123
        }
    }

    assert result == expected
