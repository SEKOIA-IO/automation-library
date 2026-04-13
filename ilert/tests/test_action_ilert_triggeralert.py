# coding: utf-8

# third parties
import requests_mock

# internals
from ilert.action_ilert_trigger_alert import IlertTriggerAlertAction
from ilert.constants import DEFAULT_EVENTS_URL


def test_ilert_postalert_default():
    integration_key: str = "my-fake-integration-key"

    action: IlertTriggerAlertAction = IlertTriggerAlertAction()
    action.module.configuration = {"integration_key": integration_key}

    alert_uuid = "d41f8c20-7a9b-4e15-b6d3-92cc4a7f18e5"
    base_url = "https://api.sekoia.io/"
    api_key = "XKDF84729HNQP16"

    alert_info = {
        "urgency": {"current_value": 42, "display": "medium"},
        "short_id": "AL98312BKWZ",
        "entity": {"name": "Red fox"},
        "title": "Test alert for ilert",
        "alert_type": {"category": "network", "value": "c2-traffic"},
        "source": "172.16.0.5",
        "target": "example.org.fake",
        "details": "some details here",
    }
    with requests_mock.Mocker() as mock:
        mock.get(
            f"{base_url}v1/sic/alerts/{alert_uuid}",
            json=alert_info,
        )
        hook_url = f"{DEFAULT_EVENTS_URL}/{integration_key}"
        mock.post(hook_url, status_code=202)

        action.run({"alert_uuid": alert_uuid, "api_key": api_key, "base_url": base_url})

        assert mock.call_count == 2
        history = mock.request_history
        assert history[0].method == "GET"
        assert history[1].method == "POST"
        assert history[1].url == hook_url
        assert history[1].json() == alert_info
