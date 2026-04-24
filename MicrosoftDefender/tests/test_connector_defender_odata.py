from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
import requests_mock
from sekoia_automation.storage import PersistentJSON

from microsoftdefender_modules import MicrosoftDefenderModule
from microsoftdefender_modules.connector_defender_odata import (
    MicrosoftDefenderAlertsConnector,
    MicrosoftDefenderIncidentsConnector,
)

TOKEN_URL = "https://login.microsoftonline.com/tenant/oauth2/token"
TOKEN_PAYLOAD = {"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799}


def _make_connector(cls, data_storage, *, base_url: str | None = None, module_base_url: str | None = None):
    module = MicrosoftDefenderModule()
    module_config = {
        "tenant_id": "tenant",
        "app_id": "app",
        "app_secret": "secret",
    }
    if module_base_url is not None:
        module_config["base_url"] = module_base_url
    module.configuration = module_config  # type: ignore[assignment]

    connector = cls(module=module, data_path=data_storage)
    connector.log = Mock()
    connector.log_exception = Mock()
    connector.push_events_to_intakes = Mock()

    connector.configuration = {
        "intake_key": "ik",
        "frequency": 60,
        "start_time": 1,
        "base_url": base_url,
    }
    return connector


@pytest.fixture
def alerts_connector(data_storage):
    return _make_connector(
        MicrosoftDefenderAlertsConnector,
        data_storage,
        base_url="https://api-eu.securitycenter.microsoft.com",
    )


@pytest.fixture
def incidents_connector(data_storage):
    return _make_connector(
        MicrosoftDefenderIncidentsConnector,
        data_storage,
        base_url="https://api-eu.security.microsoft.com",
    )


def _alert_payload(alert_id: str, ts: str) -> dict:
    return {
        "id": alert_id,
        "incidentId": 63944,
        "severity": "Informational",
        "status": "Resolved",
        "title": "Automated investigation started manually",
        "alertCreationTime": "2025-10-28T14:18:29.2966667Z",
        "lastUpdateTime": ts,
        "machineId": "f8ecffca6251f31cd73a08110ab8676212399508",
    }


def _incident_payload(incident_id: int, ts: str) -> dict:
    return {
        "incidentId": incident_id,
        "incidentName": "Email messages removed after delivery",
        "createdTime": "2026-04-07T08:58:46.6633333Z",
        "lastUpdateTime": ts,
        "status": "Resolved",
        "severity": "Informational",
        "alerts": [],
    }


def test_alerts_connector_hits_alerts_endpoint(alerts_connector):
    with requests_mock.Mocker() as mock:
        mock.get(TOKEN_URL, json=TOKEN_PAYLOAD)
        mock.get(
            "https://api-eu.securitycenter.microsoft.com/api/alerts",
            json={"value": [_alert_payload("a1", "2026-04-10T12:00:00.000Z")]},
        )

        start = datetime(2026, 4, 1, tzinfo=timezone.utc)
        batches = list(alerts_connector.fetch_events(start))

        assert len(batches) == 1
        assert batches[0][0]["id"] == "a1"
        alerts_call = next(r for r in mock.request_history if "/api/alerts" in r.url)
        assert "lastupdatetime gt" in alerts_call.qs["$filter"][0]


def test_incidents_connector_hits_incidents_endpoint(incidents_connector):
    with requests_mock.Mocker() as mock:
        mock.get(TOKEN_URL, json=TOKEN_PAYLOAD)
        mock.get(
            "https://api-eu.security.microsoft.com/api/incidents",
            json={"value": [_incident_payload(67272, "2026-04-09T09:02:23.25Z")]},
        )

        start = datetime(2026, 4, 1, tzinfo=timezone.utc)
        batches = list(incidents_connector.fetch_events(start))

        assert len(batches) == 1
        assert batches[0][0]["incidentId"] == 67272


def test_pagination_follows_odata_next_link(alerts_connector):
    with requests_mock.Mocker() as mock:
        mock.get(TOKEN_URL, json=TOKEN_PAYLOAD)
        next_link = "https://api-eu.securitycenter.microsoft.com/api/alerts?$skip=1"
        mock.get(
            "https://api-eu.securitycenter.microsoft.com/api/alerts",
            [
                {
                    "json": {
                        "value": [_alert_payload("a1", "2026-04-10T12:00:00.000Z")],
                        "@odata.nextLink": next_link,
                    }
                },
            ],
        )
        mock.get(
            next_link,
            json={"value": [_alert_payload("a2", "2026-04-10T12:01:00.000Z")]},
        )

        batches = list(alerts_connector.fetch_events(datetime(2026, 4, 1, tzinfo=timezone.utc)))
        ids = [e["id"] for batch in batches for e in batch]
        assert ids == ["a1", "a2"]


def test_empty_response_terminates_iteration(alerts_connector):
    with requests_mock.Mocker() as mock:
        mock.get(TOKEN_URL, json=TOKEN_PAYLOAD)
        mock.get(
            "https://api-eu.securitycenter.microsoft.com/api/alerts",
            json={"value": []},
        )

        batches = list(alerts_connector.fetch_events(datetime(2026, 4, 1, tzinfo=timezone.utc)))
        assert batches == []


def test_connector_uses_module_base_url_when_none_at_connector_level(data_storage):
    connector = _make_connector(
        MicrosoftDefenderAlertsConnector,
        data_storage,
        base_url=None,
        module_base_url="https://eu.api.security.microsoft.com",
    )
    assert connector.base_url == "https://eu.api.security.microsoft.com"


def test_connector_base_url_overrides_module(data_storage):
    connector = _make_connector(
        MicrosoftDefenderAlertsConnector,
        data_storage,
        base_url="https://api-eu.securitycenter.microsoft.com",
        module_base_url="https://eu.api.security.microsoft.com",
    )
    assert connector.base_url == "https://api-eu.securitycenter.microsoft.com"


def test_checkpoint_roundtrip(alerts_connector, data_storage):
    cursor = datetime(2026, 4, 10, tzinfo=timezone.utc)
    alerts_connector._save_checkpoint(cursor)
    assert alerts_connector._load_checkpoint() == cursor


def test_checkpoint_clamped_to_30_days(alerts_connector, data_storage):
    context = PersistentJSON("context.json", data_storage)
    old = datetime.now(timezone.utc) - timedelta(days=90)
    with context as cache:
        cache[alerts_connector.checkpoint_key] = old.isoformat()

    loaded = alerts_connector._load_checkpoint()
    now = datetime.now(timezone.utc)
    assert (now - loaded) <= timedelta(days=30, minutes=1)


def test_checkpoint_default_uses_start_time(alerts_connector):
    alerts_connector.configuration.start_time = 2
    loaded = alerts_connector._load_checkpoint()
    now = datetime.now(timezone.utc)
    # within a small margin of now - 2h
    assert (now - loaded) <= timedelta(hours=2, minutes=1)
    assert (now - loaded) >= timedelta(hours=1, minutes=59)


def test_alerts_and_incidents_have_separate_checkpoint_keys():
    assert MicrosoftDefenderAlertsConnector.checkpoint_key != MicrosoftDefenderIncidentsConnector.checkpoint_key


def test_token_resource_matches_connector_base_url(alerts_connector):
    with requests_mock.Mocker() as mock:
        mock.get(TOKEN_URL, json=TOKEN_PAYLOAD)
        mock.get(
            "https://api-eu.securitycenter.microsoft.com/api/alerts",
            json={"value": []},
        )

        list(alerts_connector.fetch_events(datetime(2026, 4, 1, tzinfo=timezone.utc)))

        token_request = next(r for r in mock.request_history if "oauth2/token" in r.url)
        assert "resource=https%3A%2F%2Fapi-eu.securitycenter.microsoft.com" in token_request.text
