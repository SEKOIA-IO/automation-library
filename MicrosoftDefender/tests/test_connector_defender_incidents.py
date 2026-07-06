from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest
from sekoia_automation.storage import PersistentJSON

from microsoftdefender_modules import MicrosoftDefenderModule
from microsoftdefender_modules.connector_defender_incidents import MicrosoftDefenderGraphAPIIncidents

INCIDENTS_URL = "https://graph.microsoft.com/v1.0/security/incidents"


@pytest.fixture
def trigger(data_storage):
    module = MicrosoftDefenderModule()
    module.configuration = {
        "tenant_id": "tenant",
        "app_id": "app",
        "app_secret": "secret",
    }
    trigger = MicrosoftDefenderGraphAPIIncidents(module=module, data_path=data_storage)
    trigger.log = Mock()
    trigger.log_exception = Mock()
    trigger.push_events_to_intakes = Mock()
    trigger.configuration = {
        "intake_key": "ik",
        "frequency": 60,
        "start_time": 0,
        "timedelta": 0,
    }
    yield trigger


@pytest.fixture
def now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def start_time(now) -> datetime:
    return now - timedelta(minutes=1)


@pytest.fixture
def end_time(now) -> datetime:
    return now


def _incident(incident_id: str, ts: str) -> dict:
    # Truncated form of the example payload at
    # https://learn.microsoft.com/en-us/graph/api/security-list-incidents
    return {
        "id": incident_id,
        "tenantId": "fbbe061c-9b3d-4c44-95e7-714e319b60f6",
        "status": "active",
        "displayName": "Multi-stage incident involving Execution & Command and control on one endpoint",
        "createdDateTime": ts,
        "lastUpdateDateTime": ts,
        "severity": "high",
        "classification": "truePositive",
        "determination": "multiStagedAttack",
        "comments": [],
    }


def _mock_msal_patch():
    return patch("microsoftdefender_modules.client.auth.msal.ConfidentialClientApplication")


def test_fetch_events_hits_incidents_endpoint(trigger, requests_mock, start_time, end_time):
    with _mock_msal_patch() as mock_msal:
        mock_msal.acquire_token_silent = MagicMock(return_value={"access_token": "TOKEN"})
        trigger._get_access_token = Mock()  # type: ignore[attr-defined]

        requests_mock.get(
            INCIDENTS_URL,
            json={"value": [_incident("29", "2026-04-09T09:02:23.25Z")]},
        )

        batches = list(trigger.fetch_events(start_time, end_time))

        assert len(batches) == 1
        assert batches[0][0]["id"] == "29"

        call = requests_mock.last_request
        # requests_mock lowercases qs keys and values
        assert "createddatetime gt" in call.qs["$filter"][0]
        assert "createddatetime le" in call.qs["$filter"][0]
        # incidents are never expanded with nested alerts
        assert "$expand" not in call.qs


def test_pagination_follows_next_link(trigger, requests_mock, start_time, end_time):
    with _mock_msal_patch() as mock_msal:
        mock_msal.acquire_token_silent = MagicMock(return_value={"access_token": "TOKEN"})
        trigger._get_access_token = Mock()  # type: ignore[attr-defined]

        next_url = "https://graph.microsoft.com/v1.0/security/incidents?$skip=100"
        requests_mock.get(
            INCIDENTS_URL,
            [
                {
                    "json": {
                        "value": [_incident("1", "2026-04-09T09:02:23.25Z")],
                        "@odata.nextLink": next_url,
                    }
                },
            ],
        )
        requests_mock.get(
            next_url,
            json={"value": [_incident("2", "2026-04-09T09:03:00.00Z")]},
        )

        batches = list(trigger.fetch_events(start_time, end_time))
        ids = [e["id"] for batch in batches for e in batch]
        assert ids == ["1", "2"]


def test_empty_response_terminates_iteration(trigger, requests_mock, start_time, end_time):
    with _mock_msal_patch() as mock_msal:
        mock_msal.acquire_token_silent = MagicMock(return_value={"access_token": "TOKEN"})
        trigger._get_access_token = Mock()  # type: ignore[attr-defined]

        requests_mock.get(INCIDENTS_URL, json={"value": []})

        assert list(trigger.fetch_events(start_time, end_time)) == []


def test_process_events_skips_already_seen_incidents(trigger):
    trigger.events_cache["seen"] = True

    batch = [_incident("seen", "2026-04-09T09:02:23.25Z"), _incident("fresh", "2026-04-09T09:03:00.00Z")]
    yielded = list(trigger.process_events(batch))

    assert [e["id"] for e in yielded] == ["fresh"]


def test_separate_cursor_key_from_alerts():
    assert MicrosoftDefenderGraphAPIIncidents.context_cursor_key == "most_recent_date_requested_incidents"
    assert MicrosoftDefenderGraphAPIIncidents.events_cache_context_key == "incidents_events_cache"


def test_stepper_uses_incidents_cursor(trigger, data_storage):
    fixed_now = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    cursor = fixed_now - timedelta(hours=6)

    context = PersistentJSON("context.json", data_storage)
    with context as cache:
        cache["most_recent_date_requested_incidents"] = cursor.isoformat()
        # alerts cursor must be ignored
        cache["most_recent_date_requested"] = (fixed_now - timedelta(days=1)).isoformat()

    with patch("microsoftdefender_modules.connector_base.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert trigger.stepper.start == cursor
