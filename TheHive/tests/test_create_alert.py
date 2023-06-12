import json
from typing import Any

from thehive.create_alert import TheHiveCreateAlert

ALERT: dict[str, Any] = {
    "uuid": "4764296a-f8d5-485f-92f1-bf4b28885ef6",
    "short_id": "AL123456789",
    "urgency": {"severity": 95},
    "created_at": "1643972499",
    "title": "An Alert",
    "details": "Lorem ipsum dolor",
    "alert_type": {"category": "information-gathering", "value": "scanner"},
    "stix": {},
}

ALERT_EVENTS: list[dict[str, Any]] = [
    {
        "source.ip": "1.2.3.4",
    },
    {
        "source.ip": "6.7.8.9",
    },
]


def test_create_alert_action_success(requests_mock):
    mock_alert = requests_mock.post(url="https://thehive-project.org/api/alert", json={})

    action = TheHiveCreateAlert()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    result = action.run({"alert": ALERT})
    assert not action._error
    assert result is not None
    assert mock_alert.call_count == 1


def test_create_alert_with_artifacts(requests_mock):
    mock_alert = requests_mock.post(url="https://thehive-project.org/api/alert", json={})

    action = TheHiveCreateAlert()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    result = action.run({"alert": ALERT, "events": ALERT_EVENTS})

    assert not action._error
    assert result is not None
    assert mock_alert.call_count == 1
    json_sent = json.loads(mock_alert.request_history[0]._request.body)
    assert json_sent["artifacts"][0]["dataType"] == "ip"
    assert json_sent["artifacts"][0]["tags"] == ["sekoia:type=source.ip"]
    assert json_sent["artifacts"][0]["data"] == ALERT_EVENTS[0]["source.ip"]
    assert json_sent["artifacts"][1]["data"] == ALERT_EVENTS[1]["source.ip"]


def test_create_alert_action_api_error(requests_mock):
    mock_alert = requests_mock.post(url="https://thehive-project.org/api/alert", status_code=500)

    action = TheHiveCreateAlert()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    result = action.run({"alert": ALERT})

    assert action._error
    assert not result
    assert mock_alert.call_count == 1
