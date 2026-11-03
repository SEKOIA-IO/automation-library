import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import orjson
import pytest
import requests
import requests_mock

from cyberark_modules import CyberArkModule
from cyberark_modules.client.auth import AuthorizationFailedException
from cyberark_modules.connector_audit_logs import (
    CursorExpiredError,
    CyberArkAuditLogsConnector,
    CyberArkAuditLogsConnectorConfiguration,
)


@pytest.fixture
def trigger(data_storage):
    module = CyberArkModule()
    module.configuration = {
        "auth_base_url": "https://example.id.cyberark.cloud",
        "login_name": "login",
        "password": "qwerty",
        "application_id": "MyApp1",
    }

    trigger = CyberArkAuditLogsConnector(module=module, data_path=data_storage)
    # don't wait for the API rate limit in tests
    trigger.API_RATELIMIT_PER_MINUTE = 1000
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = {
        "api_base_url": "https://example.cyberark.cloud",
        "api_key": "APIKEY1234",
        "intake_key": "intake_key",
    }
    yield trigger


@pytest.fixture
def events1():
    return [
        {
            "uuid": "20fced38-7a82-4e32-8ca7-3ca599dac97b",
            "tenantId": "c1ff0b56-1b0a-4409-9226-80bee50ef8cf",
            "timestamp": 1739921924719,
            "username": "PVWAGWUser",
            "applicationCode": "PAM",
            "auditCode": "PAM00088",
            "auditType": "Info",
            "action": "Set Password",
            "userId": "PVWAGWUser",
            "source": "PVWAAPP",
            "actionType": "Password",
            "component": "Vault",
            "serviceName": "Privilege Cloud",
            "accessMethod": None,
            "accountId": "",
            "target": "",
            "command": None,
            "sessionId": None,
            "message": "",
            "customData": {"PAM": {"new_target": "", "target": ""}},
            "cloudProvider": None,
            "cloudWorkspacesAndRoles": [],
            "cloudIdentities": None,
            "cloudAssets": None,
            "safe": "",
            "accountName": "",
            "targetPlatform": "",
            "targetAccount": "",
            "identityType": None,
        }
    ]


@pytest.fixture
def message1(events1):
    return {
        "data": events1,
        "paging": {"cursor": {"cursorRef": "secondPageCursor"}},
    }


@pytest.fixture
def message2():
    return {"data": [], "paging": {"cursor": {"cursorRef": "secondPageCursor"}}}


def test_fetch_events(trigger, message1, message2, events1):
    trigger.from_date = 1739921924000

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://example.id.cyberark.cloud/oauth2/token/MyApp1",
            status_code=200,
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.post(
            "https://example.cyberark.cloud/api/audits/stream/createQuery",
            status_code=200,
            json={"cursorRef": "cursorRef"},
        )

        mock_requests.post(
            "https://example.cyberark.cloud/api/audits/stream/results",
            [
                {"status_code": 200, "json": message1},
                {"status_code": 200, "json": message2},
            ],
        )
        events = trigger.fetch_events()

        assert list(events) == [events1]
        assert trigger.from_date == 1739921924719
        assert trigger.cursor_checkpoint.offset == "secondPageCursor"


def test_next_batch_sleep_until_next_round(trigger, message1, message2):
    with patch("cyberark_modules.connector_audit_logs.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://example.id.cyberark.cloud/oauth2/token/MyApp1",
            status_code=200,
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.post(
            "https://example.cyberark.cloud/api/audits/stream/createQuery",
            status_code=200,
            json={"cursorRef": "cursorRef"},
        )

        mock_requests.post(
            "https://example.cyberark.cloud/api/audits/stream/results",
            [
                {"status_code": 200, "json": message1},
                {"status_code": 200, "json": message2},
            ],
        )

        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 1


def test_authorization_error(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://example.id.cyberark.cloud/oauth2/token/MyApp1",
            status_code=400,
            json={"error": "Auth error", "code": "<CODE>", "description": "Some description"},
        )
        with pytest.raises(AuthorizationFailedException):
            trigger.next_batch()


def test_authorization_error_without_details(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://example.id.cyberark.cloud/oauth2/token/MyApp1",
            status_code=400,
            json={},
        )
        with pytest.raises(AuthorizationFailedException):
            trigger.next_batch()


def test_network_error(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://example.id.cyberark.cloud/oauth2/token/MyApp1",
            status_code=500,
            json={"error": "Auth error", "code": "<CODE>", "description": "Some description"},
        )
        with pytest.raises(requests.HTTPError):
            trigger.next_batch()


def mock_token(mock_requests):
    mock_requests.post(
        "https://example.id.cyberark.cloud/oauth2/token/MyApp1",
        status_code=200,
        json={
            "access_token": "foo-token",
            "token_type": "bearer",
            "expires_in": 1799,
        },
    )


def test_create_query_uses_max_page_size(trigger, message2):
    with requests_mock.Mocker() as mock_requests:
        mock_token(mock_requests)
        create_query = mock_requests.post(
            "https://example.cyberark.cloud/api/audits/stream/createQuery",
            status_code=200,
            json={"cursorRef": "cursorRef"},
        )
        mock_requests.post("https://example.cyberark.cloud/api/audits/stream/results", json=message2)

        assert list(trigger.fetch_events()) == []
        assert create_query.last_request.json()["query"]["pageSize"] == 500


def test_checkpoint_saved_per_page(trigger, message1, events1):
    trigger.from_date = 1739921924000

    with requests_mock.Mocker() as mock_requests:
        mock_token(mock_requests)
        mock_requests.post(
            "https://example.cyberark.cloud/api/audits/stream/createQuery",
            status_code=200,
            json={"cursorRef": "cursorRef"},
        )
        mock_requests.post(
            "https://example.cyberark.cloud/api/audits/stream/results",
            [
                {"status_code": 200, "json": message1},
                {"status_code": 429, "json": {"message": "Too Many Requests"}, "reason": "Too Many Requests"},
            ],
        )

        events = trigger.fetch_events()
        assert next(events) == events1
        with pytest.raises(requests.HTTPError):
            next(events)

    # the first page was forwarded, so the checkpoint must have moved despite the error
    assert trigger.from_date == 1739921924719
    assert trigger.cursor_checkpoint.offset == "secondPageCursor"
    assert events1[0]["uuid"] in trigger.load_events_cache()


def test_handle_response_error_message(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://example.cyberark.cloud/api/audits/stream/results",
            status_code=429,
            reason="Too Many Requests",
            json={"code": "RATE_LIMIT", "message": "Too Many Requests", "description": "Slow down"},
        )
        response = requests.post("https://example.cyberark.cloud/api/audits/stream/results")

        with pytest.raises(requests.HTTPError):
            trigger._handle_response_error(response)

    trigger.log.assert_called_once_with(
        message=(
            "Request to CyberArk API failed with status 429 - Too Many Requests"
            " error_code=RATE_LIMIT error_message=Too Many Requests error_description=Slow down"
        ),
        level="error",
    )


def test_run_waits_after_error(trigger):
    with patch("cyberark_modules.connector_audit_logs.time") as mock_time, patch.object(
        CyberArkAuditLogsConnector, "running", new_callable=PropertyMock
    ) as mock_running, patch.object(trigger, "next_batch", side_effect=requests.HTTPError("429")):
        mock_running.side_effect = [True, False]

        trigger.run()

        trigger.log_exception.assert_called_once()
        mock_time.sleep.assert_called_once_with(trigger.ERROR_BACKOFF_SECONDS)


CREATE_QUERY_URL = "https://example.cyberark.cloud/api/audits/stream/createQuery"
RESULTS_URL = "https://example.cyberark.cloud/api/audits/stream/results"


def test_reuse_stored_cursor(trigger, message1, message2, events1):
    trigger.cursor_checkpoint.offset = "storedCursor"

    with requests_mock.Mocker() as mock_requests:
        mock_token(mock_requests)
        create_query = mock_requests.post(CREATE_QUERY_URL, json={"cursorRef": "cursorRef"})
        results = mock_requests.post(RESULTS_URL, [{"json": message1}, {"json": message2}])

        assert list(trigger.fetch_events()) == [events1]

        assert create_query.call_count == 0
        assert [request.json() for request in results.request_history] == [
            {"cursorRef": "storedCursor"},
            {"cursorRef": "secondPageCursor"},
        ]
    assert trigger.cursor_checkpoint.offset == "secondPageCursor"


def test_empty_page_keeps_cursor(trigger):
    trigger.cursor_checkpoint.offset = "storedCursor"

    with requests_mock.Mocker() as mock_requests:
        mock_token(mock_requests)
        mock_requests.post(RESULTS_URL, json={"data": [], "paging": {"cursor": {"cursorRef": "nextCursor"}}})

        assert list(trigger.fetch_events()) == []

    assert trigger.cursor_checkpoint.offset == "nextCursor"


def test_recreate_query_when_stored_cursor_rejected(trigger, message1, message2, events1):
    trigger.from_date = 1739921924000
    trigger.cursor_checkpoint.offset = "expiredCursor"

    with requests_mock.Mocker() as mock_requests:
        mock_token(mock_requests)
        create_query = mock_requests.post(CREATE_QUERY_URL, json={"cursorRef": "newCursor"})
        results = mock_requests.post(
            RESULTS_URL,
            [{"status_code": 403, "reason": "Forbidden"}, {"json": message1}, {"json": message2}],
        )

        assert list(trigger.fetch_events()) == [events1]

        assert create_query.call_count == 1
        assert create_query.last_request.json()["query"]["filterModel"]["date"]["dateFrom"].startswith(
            "2025-02-18T23:38:44"
        )
        assert [request.json()["cursorRef"] for request in results.request_history] == [
            "expiredCursor",
            "newCursor",
            "secondPageCursor",
        ]
    assert trigger.cursor_checkpoint.offset == "secondPageCursor"
    assert any(call.kwargs.get("level") == "warning" for call in trigger.log.call_args_list)


def test_new_cursor_rejected_raises(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_token(mock_requests)
        create_query = mock_requests.post(CREATE_QUERY_URL, json={"cursorRef": "newCursor"})
        mock_requests.post(RESULTS_URL, status_code=403, reason="Forbidden")

        with pytest.raises(CursorExpiredError):
            list(trigger.fetch_events())

        assert create_query.call_count == 1
    assert any(call.kwargs.get("level") == "critical" for call in trigger.log.call_args_list)


def test_recreated_cursor_rejected_raises(trigger):
    trigger.cursor_checkpoint.offset = "expiredCursor"

    with requests_mock.Mocker() as mock_requests:
        mock_token(mock_requests)
        create_query = mock_requests.post(CREATE_QUERY_URL, json={"cursorRef": "newCursor"})
        results = mock_requests.post(RESULTS_URL, status_code=403, reason="Forbidden")

        with pytest.raises(CursorExpiredError):
            list(trigger.fetch_events())

        # only one attempt to recreate the query
        assert create_query.call_count == 1
        assert results.call_count == 2


def test_create_query_forbidden(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_token(mock_requests)
        mock_requests.post(CREATE_QUERY_URL, status_code=403, reason="Forbidden", json={})
        results = mock_requests.post(RESULTS_URL, json={})

        with pytest.raises(requests.HTTPError):
            list(trigger.fetch_events())

        assert results.call_count == 0
    trigger.log.assert_called_once_with(
        message="Request to CyberArk API failed with status 403 - Forbidden", level="critical"
    )


def test_migration_from_timestamp_only_checkpoint(data_storage, message2):
    # a context written by the previous version only contains the timestamp
    recent = (datetime.now(timezone.utc) - timedelta(minutes=10)).replace(microsecond=0)
    with open(Path(data_storage) / "context.json", "w") as f:
        json.dump({"most_recent_date_seen": recent.isoformat(), "events_cache": []}, f)

    module = CyberArkModule()
    module.configuration = {
        "auth_base_url": "https://example.id.cyberark.cloud",
        "login_name": "login",
        "password": "qwerty",
        "application_id": "MyApp1",
    }
    trigger = CyberArkAuditLogsConnector(module=module, data_path=Path(data_storage))
    trigger.API_RATELIMIT_PER_MINUTE = 1000
    trigger.log = MagicMock()
    trigger.configuration = {
        "api_base_url": "https://example.cyberark.cloud",
        "api_key": "APIKEY1234",
        "intake_key": "intake_key",
    }

    with requests_mock.Mocker() as mock_requests:
        mock_token(mock_requests)
        create_query = mock_requests.post(CREATE_QUERY_URL, json={"cursorRef": "newCursor"})
        mock_requests.post(RESULTS_URL, json=message2)

        assert list(trigger.fetch_events()) == []

        date_from = create_query.last_request.json()["query"]["filterModel"]["date"]["dateFrom"]
        assert datetime.fromisoformat(date_from) == recent
    assert trigger.cursor_checkpoint.offset == "secondPageCursor"


def test_failed_push_does_not_lose_events(trigger, message1, message2, events1):
    trigger.cursor_checkpoint.offset = "storedCursor"
    trigger.push_events_to_intakes.side_effect = [Exception("intake unavailable"), None]

    with patch("cyberark_modules.connector_audit_logs.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_time.time.return_value = 1666711174.0
        mock_token(mock_requests)
        mock_requests.post(RESULTS_URL, [{"json": message1}, {"json": message1}, {"json": message2}])

        # the push fails: nothing must be marked as seen nor checkpointed
        with pytest.raises(Exception, match="intake unavailable"):
            trigger.next_batch()

        assert events1[0]["uuid"] not in trigger.events_cache
        assert trigger.cursor_checkpoint.offset == "storedCursor"

        # the retry fetches the same page again and forwards its events
        trigger.next_batch()

    assert trigger.push_events_to_intakes.call_count == 2
    assert trigger.push_events_to_intakes.call_args_list[1].kwargs["events"] == [
        orjson.dumps(event).decode("utf-8") for event in events1
    ]
    assert events1[0]["uuid"] in trigger.events_cache
    assert trigger.cursor_checkpoint.offset == "secondPageCursor"


def test_checkpoint_consistent_across_pages_and_restart(trigger, data_storage, events1):
    trigger.from_date = 1739921924000

    def page(index: int, cursor_ref: str) -> dict:
        event = {**events1[0], "uuid": f"uuid-{index}", "timestamp": 1739921924000 + index * 1000}
        return {"data": [event], "paging": {"cursor": {"cursorRef": cursor_ref}}}

    with requests_mock.Mocker() as mock_requests:
        mock_token(mock_requests)
        mock_requests.post(CREATE_QUERY_URL, json={"cursorRef": "cursor0"})
        mock_requests.post(
            RESULTS_URL,
            [
                {"json": page(1, "cursor1")},
                {"json": page(2, "cursor2")},
                {"json": page(3, "cursor3")},
                {"json": {"data": [], "paging": {"cursor": {"cursorRef": "cursor4"}}}},
            ],
        )

        assert len(list(trigger.fetch_events())) == 3

    # the context on disk must hold the cursor, the timestamp and the events cache of the last page
    with open(Path(data_storage) / "context.json") as f:
        context = json.load(f)

    assert context["cursor"] == "cursor4"
    assert datetime.fromisoformat(context["most_recent_date_seen"]) == datetime.fromtimestamp(
        1739921927, tz=timezone.utc
    )
    assert set(context["events_cache"]) == {"uuid-1", "uuid-2", "uuid-3"}

    # a restarted connector resumes from the same state
    restarted = CyberArkAuditLogsConnector(module=trigger.module, data_path=Path(data_storage))
    assert restarted.cursor_checkpoint.offset == "cursor4"
    assert set(restarted.events_cache.keys()) == {"uuid-1", "uuid-2", "uuid-3"}
