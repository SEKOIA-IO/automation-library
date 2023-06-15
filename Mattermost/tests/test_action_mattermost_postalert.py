# coding: utf-8

# natives
import json

# third parties
import requests_mock

# internals
from mattermost.action_mattermost_postalert import MattermostPostAlertAction


def test_mattermost_postalert_default():
    hook_url: str = "https://my.chat.mattermost/hooks/123456"

    mt: MattermostPostAlertAction = MattermostPostAlertAction()
    mt.module.configuration = {"hook_url": hook_url}

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
        mock.post(hook_url, text="ok")

        mt.run({"alert_uuid": alert_uuid, "api_key": api_key, "base_url": base_url})

        assert mock.call_count == 2
        history = mock.request_history
        # first call was to fetch the alert
        assert history[0].method == "GET"
        # second call was to post the message
        assert history[1].method == "POST"
        assert history[1].url == hook_url
        assert json.loads(history[1].text) == {
            "attachments": [
                {
                    "author_name": "Blue boat",
                    "color": "#1c8d00",
                    "fallback": "Super test alert",
                    "fields": [
                        {
                            "short": True,
                            "title": "Alert type",
                            "value": "malicious-code - malware",
                        },
                        {"short": True, "title": "Urgency", "value": "low - 10"},
                        {"short": True, "title": "Source", "value": "10.10.10.10"},
                        {"short": True, "title": "Target", "value": "test.com.fake"},
                        {
                            "short": False,
                            "title": "Description",
                            "value": "no detail provided",
                        },
                    ],
                    "pretext": None,
                    "title": "Super test alert",
                    "title_link": "https://app.sekoia.io/sic/alerts/AL13426AYUU",
                }
            ],
            "channel": None,
            "icon_url": "https://app.sekoia.io/user/favicon.ico",
            "username": "Blue boat",
        }
