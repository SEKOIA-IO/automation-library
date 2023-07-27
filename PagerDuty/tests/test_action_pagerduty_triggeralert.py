# coding: utf-8

# natives
import json

# third parties
import requests_mock

# internals
from pagerduty.action_pagerduty_trigger_alert import PagerDutyTriggerAlertAction
from pagerduty.constants import DEFAULT_EVENTSAPIV2_URL
from pagerduty.helpers import urgency_to_pagerduty_severity


def test_pagerduty_postalert_default():
    integration_key: str = "my-fake-integration-key"

    pager_action: PagerDutyTriggerAlertAction = PagerDutyTriggerAlertAction()
    pager_action.module.configuration = {"integration_key": integration_key}

    alert_uuid = "bec203a3-bc70-4430-80ad-f72fe11f3ad8"
    base_url = "https://api.sekoia.io/"
    api_key = "AZERTYUI987654345678"

    alert_info = {
        "urgency": {"current_value": 10, "display": "low"},
        "short_id": "AL13426AYUU",
        "entity": {"name": "Blue boat"},
        "title": "Super test alert",
        "alert_type": {"category": "malicious-code", "value": "malware"},
        "source": "10.10.10.10",
        "target": "test.com.fake",
        "details": "no detail provided",
    }
    with requests_mock.Mocker() as mock:
        mock.get(
            f"{base_url}v1/sic/alerts/{alert_uuid}",
            json=alert_info,
        )
        hook_url = pager_action.module.configuration.get("integration_url", DEFAULT_EVENTSAPIV2_URL)
        mock.post(
            hook_url,
            json={
                "status": "success",
                "message": "Event processed",
                "dedup_key": alert_info["short_id"],
            },
        )

        pager_action.run({"alert_uuid": alert_uuid, "api_key": api_key, "base_url": base_url})

        assert mock.call_count == 2
        history = mock.request_history
        # first call was to fetch the alert
        assert history[0].method == "GET"
        # second call was to post the message
        assert history[1].method == "POST"
        assert history[1].url == hook_url
        assert json.loads(history[1].text) == {
            "payload": {
                "summary": alert_info["title"],
                "source": alert_info["entity"]["name"],
                "severity": urgency_to_pagerduty_severity(alert_info["urgency"]["current_value"]),
                "class": f"{alert_info['alert_type']['category']} - {alert_info['alert_type']['value']}",
                "custom_details": {
                    "source": alert_info.get("source"),
                    "target": alert_info["target"],
                    "details": alert_info["details"],
                },
            },
            "routing_key": integration_key,
            "dedup_key": alert_info["short_id"],
            "images": [
                {
                    "src": "https://app.sekoia.io/assets/logos/sekoiaio-black.svg",
                    "href": "https://app.sekoia.io/",
                    "alt": "Sekoia.io",
                }
            ],
            "links": [
                {
                    "href": f"https://app.sekoia.io/sic/alerts/{alert_info['short_id']}",
                    "text": "Alert details",
                }
            ],
            "event_action": "trigger",
            "client": "Sekoia.io Security Service",
            "client_url": "https://app.sekoia.io",
        }
