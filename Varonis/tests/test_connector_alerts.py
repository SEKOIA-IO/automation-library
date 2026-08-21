from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests_mock
from sekoia_automation.storage import PersistentJSON

from varonis_modules import VaronisModule
from varonis_modules.connector_varonis_saas_alerts import VaronisSaaSAlertsConnector


@pytest.fixture
def trigger(data_storage):
    module = VaronisModule()
    module.configuration = {
        "base_url": "https://test.varonis.io",
        "api_key": "API_KEY",
    }
    trigger = VaronisSaaSAlertsConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = {
        "intake_key": "intake_key",
        "frequency": 60,
        "start_time": 0,
        "timedelta": 0,
    }

    yield trigger


@pytest.fixture
def response_1():
    return {
        "data": {
            "alertsAsync": {
                "jobId": "11111111-1111-1111-1111-111111111111",
                "jobStatus": "PENDING",
                "results": None,
            }
        }
    }


@pytest.fixture
def response_2():
    return {
        "data": {
            "alertsQueryJob": {
                "jobId": "11111111-1111-1111-1111-111111111111",
                "jobStatus": "COMPLETED",
                "jobProgress": None,
                "results": [
                    {
                        "escalationType": None,
                        "eventsCount": 1,
                        "hasSensitiveResource": False,
                        "hasTaggedResource": False,
                        "id": "22222222-2222-2222-2222-222222222222",
                        "isAssignedToVaronis": False,
                        "status": "NEW",
                        "dataSource": [
                            {
                                "id": "3",
                                "name": "https://example.com",
                                "type": "SHARE_POINT_ONLINE",
                            }
                        ],
                        "policy": {
                            "id": "338",
                            "name": "Eicar test",
                            "severity": "HIGH",
                            "category": "INTRUSION",
                        },
                        "generationTime": {"dateTimeUtc": "2026-06-16T14:06:54.000Z"},
                    },
                    {
                        "escalationType": None,
                        "eventsCount": 1,
                        "hasSensitiveResource": False,
                        "hasTaggedResource": False,
                        "id": "33333333-3333-3333-3333-333333333333",
                        "isAssignedToVaronis": False,
                        "status": "NEW",
                        "dataSource": [
                            {
                                "id": "3",
                                "name": "https://example.com",
                                "type": "SHARE_POINT_ONLINE",
                            }
                        ],
                        "policy": {
                            "id": "338",
                            "name": "Eicar test",
                            "severity": "HIGH",
                            "category": "INTRUSION",
                        },
                        "generationTime": {"dateTimeUtc": "2026-06-16T14:03:16.000Z"},
                    },
                ],
            }
        }
    }


@pytest.fixture
def trigger_activation() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
def end_time(trigger_activation: datetime) -> datetime:
    return trigger_activation


@pytest.fixture
def start_time(trigger_activation: datetime) -> datetime:
    return trigger_activation - timedelta(minutes=1)


def test_fetch_events(
    trigger,
    response_1: dict,
    response_2: dict,
    start_time: datetime,
    end_time: datetime,
) -> None:
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://test.varonis.io/api/authentication/api_keys/token",
            status_code=200,
            json={
                "access_token": "access_token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )

        mock_requests.post(
            "https://test.varonis.io/api/graphql",
            [
                {"status_code": 200, "json": response_1},
                {"status_code": 200, "json": response_2},
            ],
        )

        events = list(trigger.fetch_events(from_date=start_time, to_date=end_time))
        assert len(events) == 2


def test_stepper_with_cursor(trigger, data_storage):
    date = datetime.now(UTC)
    most_recent_date_requested = date - timedelta(days=6)
    context = PersistentJSON("context.json", data_storage)

    with context as cache:
        cache["most_recent_date_requested"] = most_recent_date_requested.isoformat()

    with patch(
        "varonis_modules.connector_varonis_saas_alerts.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = datetime.now(UTC)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert trigger.stepper.start == most_recent_date_requested


def test_stepper_with_cursor_older_than_week(trigger, data_storage):
    context = PersistentJSON("context.json", data_storage)

    fixed_now = datetime(2026, 3, 16, 1, 12, 0, tzinfo=UTC)
    most_recent_date_requested = fixed_now - timedelta(days=40)
    expected_date = fixed_now - timedelta(days=7)

    with context as cache:
        cache["most_recent_date_requested"] = most_recent_date_requested.isoformat()

    with patch(
        "varonis_modules.connector_varonis_saas_alerts.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert trigger.stepper.start.replace(microsecond=0) == expected_date.replace(
            microsecond=0
        )


def test_stepper_without_cursor(trigger, data_storage):
    context = PersistentJSON("context.json", data_storage)

    # ensure that the cursor is None
    with context as cache:
        cache["most_recent_date_requested"] = None

    with patch(
        "sekoia_automation.helpers.timestepper.datetime.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = datetime(
            2023, 3, 22, 11, 56, 28, tzinfo=UTC
        )
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert trigger.stepper.start == datetime(
            2023, 3, 22, 11, 55, 28, tzinfo=UTC
        )
