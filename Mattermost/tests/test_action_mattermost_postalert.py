# coding: utf-8

# natives
import json

# third parties
import pytest
import requests
import requests_mock
from pydantic import ValidationError

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


@pytest.mark.parametrize("arguments", [{}, {"alert_uuid": ""}, {"alert_uuid": "   "}])
def test_mattermost_postalert_requires_alert_uuid(arguments):
    hook_url: str = "https://my.chat.mattermost/hooks/123456"

    mt: MattermostPostAlertAction = MattermostPostAlertAction()
    mt.module.configuration = {"hook_url": hook_url}
    arguments.setdefault("api_key", "AZERTYUI987654345678")
    arguments.setdefault("base_url", "https://api.sekoia.io/")

    with requests_mock.Mocker() as mock:
        with pytest.raises(ValidationError):
            mt.run(arguments)

    assert mock.call_count == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("alert_uuid", "not-a-uuid"),
        ("alert_uuid", "AL"),
        ("alert_uuid", "AL   "),
        ("alert_uuid", "ALx-y"),
        ("alert_uuid", "ALgarbage"),
        ("alert_uuid", "AL13426AYUU"),
        ("base_url", "not a url"),
        ("base_url", "https://api.sekoia.io/?tenant=x"),
        ("base_url", "https://api.sekoia.io/#fragment"),
        ("api_key", ""),
    ],
)
def test_mattermost_postalert_rejects_invalid_arguments(field, value):
    hook_url: str = "https://my.chat.mattermost/hooks/123456"

    mt: MattermostPostAlertAction = MattermostPostAlertAction()
    mt.module.configuration = {"hook_url": hook_url}
    arguments = {
        "alert_uuid": "bec203a3-bc70-4430-80ad-f72fe11f3ad8",
        "api_key": "AZERTYUI987654345678",
        "base_url": "https://api.sekoia.io/",
    }
    arguments[field] = value

    with requests_mock.Mocker() as mock:
        with pytest.raises(ValidationError):
            mt.run(arguments)

    assert mock.call_count == 0


def test_mattermost_postalert_accepts_short_id():
    hook_url: str = "https://my.chat.mattermost/hooks/123456"

    mt: MattermostPostAlertAction = MattermostPostAlertAction()
    mt.module.configuration = {"hook_url": hook_url}

    alert_short_id = "AL13426AYUU7"
    base_url = "https://api.sekoia.io/"
    api_key = "AZERTYUI987654345678"

    alert_info = {
        "urgency": {"current_value": 10, "display": "low"},
        "short_id": alert_short_id,
        "entity": {"name": "Blue boat"},
        "title": "Super test alert",
        "alert_type": {"category": "malicious-code", "value": "malware"},
        "source": "10.10.10.10",
        "target": "test.com.fake",
        "details": "no detail provided",
    }
    with requests_mock.Mocker() as mock:
        mock.get(
            f"{base_url}v1/sic/alerts/{alert_short_id}",
            json=alert_info,
        )
        mock.post(hook_url, text="ok")

        mt.run({"alert_uuid": alert_short_id, "api_key": api_key, "base_url": base_url})

        assert mock.call_count == 2


@pytest.mark.parametrize("base_url", ["https://example.com/api/", "https://example.com/api"])
def test_mattermost_postalert_accepts_base_url_with_path_prefix(base_url):
    hook_url: str = "https://my.chat.mattermost/hooks/123456"

    mt: MattermostPostAlertAction = MattermostPostAlertAction()
    mt.module.configuration = {"hook_url": hook_url}

    alert_uuid = "bec203a3-bc70-4430-80ad-f72fe11f3ad8"
    expected_url = f"https://example.com/api/v1/sic/alerts/{alert_uuid}"

    alert_info = {
        "urgency": {"current_value": 10, "display": "low"},
        "short_id": "AL13426AYUU7",
        "entity": {"name": "Blue boat"},
        "title": "Super test alert",
        "alert_type": {"category": "malicious-code", "value": "malware"},
        "source": "10.10.10.10",
        "target": "test.com.fake",
        "details": "no detail provided",
    }
    with requests_mock.Mocker() as mock:
        mock.get(expected_url, json=alert_info)
        mock.post(hook_url, text="ok")

        mt.run({"alert_uuid": alert_uuid, "api_key": "AZERTYUI987654345678", "base_url": base_url})

        assert mock.call_count == 2
        assert mock.request_history[0].url == expected_url


ALERT_INFO = {
    "urgency": {"current_value": 100, "display": "high"},
    "short_id": "AL13426AYUU7",
    "entity": {"name": "Blue boat"},
    "title": "Super test alert",
    "alert_type": {"category": "malicious-code", "value": "malware"},
    "target": "test.com.fake",
    "details": "no detail provided",
}


def test_mattermost_postalert_with_pretext_and_channel():
    hook_url: str = "https://my.chat.mattermost/hooks/123456"

    mt: MattermostPostAlertAction = MattermostPostAlertAction()
    mt.module.configuration = {"hook_url": hook_url}

    alert_uuid = "bec203a3-bc70-4430-80ad-f72fe11f3ad8"
    base_url = "https://api.sekoia.io"
    api_key = "AZERTYUI987654345678"

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}/v1/sic/alerts/{alert_uuid}", json=ALERT_INFO)
        mock.post(hook_url, text="ok")

        result = mt.run(
            {
                "alert_uuid": alert_uuid,
                "api_key": api_key,
                "base_url": base_url,
                "channel": "sekoiaio---operation-center",
                "pretext": "New alert",
            }
        )

        assert mock.call_count == 2
        assert mock.request_history[0].headers["Authorization"] == f"Bearer {api_key}"
        posted = json.loads(mock.request_history[1].text)

    assert result == posted
    assert posted["channel"] == "sekoiaio---operation-center"
    attachment = posted["attachments"][0]
    assert attachment["pretext"] == "New alert"
    assert attachment["fallback"] == "New alert - Super test alert"
    assert attachment["color"] == "#f00"
    assert {"short": True, "title": "Source", "value": None} in attachment["fields"]
    assert {"short": True, "title": "Urgency", "value": "high - 100"} in attachment["fields"]


def test_mattermost_postalert_alert_fetch_error():
    hook_url: str = "https://my.chat.mattermost/hooks/123456"

    mt: MattermostPostAlertAction = MattermostPostAlertAction()
    mt.module.configuration = {"hook_url": hook_url}

    alert_uuid = "bec203a3-bc70-4430-80ad-f72fe11f3ad8"
    base_url = "https://api.sekoia.io/"

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}v1/sic/alerts/{alert_uuid}", status_code=404, json={"message": "not found"})
        mock.post(hook_url, text="ok")

        with pytest.raises(requests.HTTPError):
            mt.run({"alert_uuid": alert_uuid, "api_key": "AZERTYUI987654345678", "base_url": base_url})

        assert mock.call_count == 1
        assert mock.request_history[0].method == "GET"


def test_mattermost_postalert_hook_error():
    hook_url: str = "https://my.chat.mattermost/hooks/123456"

    mt: MattermostPostAlertAction = MattermostPostAlertAction()
    mt.module.configuration = {"hook_url": hook_url}

    alert_uuid = "bec203a3-bc70-4430-80ad-f72fe11f3ad8"
    base_url = "https://api.sekoia.io/"

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}v1/sic/alerts/{alert_uuid}", json=ALERT_INFO)
        mock.post(hook_url, status_code=500, text="error")

        with pytest.raises(requests.HTTPError):
            mt.run({"alert_uuid": alert_uuid, "api_key": "AZERTYUI987654345678", "base_url": base_url})

        assert mock.call_count == 2
