from typing import Any
import requests_mock

from thehive.create_alert import TheHiveCreateAlertV5

SEKOIA_BASE_URL: str = "https://app.sekoia.io"

ALERT: dict[str, Any] = {
    "uuid": "00000000-0000-0000-0000-000000000001",
    "short_id": "ALXXXXXXXXX",
    "urgency": {"severity": 95},
    "created_at": 1643972499,
    "title": "My test alert",
    "details": "Lorem ipsum dolor",
    "alert_type": {"category": "information-gathering", "value": "scanner"},
    "stix": {},
}

HIVE_OUTPUT = {
    "_id": "~00000001",
    "_type": "Alert",
    "_createdBy": "user@sekoia.io",
    "_createdAt": 1716817666129,
    "type": "my-alert",
    "source": "my-source",
    "sourceRef": "my-reference",
    "title": "My test alert",
    "description": "Just a description",
    "severity": 2,
    "date": 1716817665325,
    "tags": [],
    "tlp": 2,
    "pap": 2,
    "follow": True,
    "customFields": [],
    "observableCount": 0,
    "status": "New",
    "stage": "New",
    "extraData": {},
    "newDate": 1716817665357,
    "timeToDetect": 0,
}


def test_create_alert_action_success():
    action = TheHiveCreateAlertV5()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(url="https://thehive-project.org/api/v1/alert", status_code=200, json=HIVE_OUTPUT)

        result = action.run({"sekoia_base_url": SEKOIA_BASE_URL, "alert": ALERT})
        assert result is not None
        assert result["title"] == ALERT["title"]


def test_create_alert_action_api_error(requests_mock):
    mock_alert = requests_mock.post(url="https://thehive-project.org/api/v1/alert", status_code=500)

    action = TheHiveCreateAlertV5()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    result = action.run({"sekoia_base_url": SEKOIA_BASE_URL, "alert": ALERT})

    assert not result
    assert mock_alert.call_count == 1
