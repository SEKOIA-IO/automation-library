import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest
import requests_mock
from requests import Response

from okta_modules import OktaModule
from okta_modules.helpers import get_upper_second
from okta_modules.system_log_trigger import FetchEventsException, SystemLogConnector, compute_event_checksum


@pytest.fixture
def fake_time():
    yield datetime(2022, 11, 5, 11, 59, 59, tzinfo=timezone.utc)


@pytest.fixture
def patch_datetime_now(fake_time):
    with patch("okta_modules.system_log_trigger.datetime") as mock_datetime:
        mock_datetime.now.return_value = fake_time
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        yield mock_datetime


@pytest.fixture
def trigger(data_storage, patch_datetime_now):
    module = OktaModule()
    trigger = SystemLogConnector(module=module, data_path=data_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {"apikey": "myapikey", "base_url": "https://tenant_id.okta.com"}
    trigger.configuration = {
        "intake_key": "intake_key",
    }

    yield trigger


@pytest.fixture
def message1():
    # flake8: noqa
    return {
        "uuid": "7a353625-99c9-435b-a4b6-b1137a5e6edb",
        "actor": {
            "id": "2pHxMaUZr2yoej9R2Lsf4",
            "type": "SystemPrincipal",
            "alternateId": "system@okta.com",
            "detailEntry": None,
            "displayName": "Okta System",
        },
        "client": {
            "id": None,
            "zone": "null",
            "device": "Computer",
            "ipAddress": "1.2.3.4",
            "userAgent": {
                "os": "Windows 10",
                "browser": "CHROME",
                "rawUserAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
            },
            "geographicalContext": {
                "city": "Paris",
                "state": "Ile-de-France",
                "country": "France",
                "postalCode": None,
                "geolocation": {"lat": 48.856944, "lon": 2.351389},
            },
        },
        "device": None,
        "target": [
            {
                "id": "kdYO9RZnIHNhV6vii333b",
                "type": "AppInstance",
                "alternateId": "Org2org",
                "detailEntry": None,
                "displayName": "SAML 2.0 IdP",
            },
            {
                "id": "eWiaLPtSTpjyy1BIwNFXg",
                "type": "User",
                "alternateId": "john.doe@example.org",
                "detailEntry": None,
                "displayName": "John Doe",
            },
        ],
        "outcome": {"reason": None, "result": "SUCCESS"},
        "request": {
            "ipChain": [
                {
                    "ip": "1.2.3.4",
                    "source": None,
                    "version": "V4",
                    "geographicalContext": {
                        "city": "Paris",
                        "state": "Ile-de-France",
                        "country": "France",
                        "postalCode": None,
                        "geolocation": {"lat": 48.856944, "lon": 2.351389},
                    },
                }
            ]
        },
        "version": "0",
        "severity": "INFO",
        "eventType": "user.authentication.auth_via_IDP",
        "published": "2022-11-15T08:04:22.213Z",
        "transaction": {"id": "jI80snAs0ZMym5tvc8Jbp", "type": "WEB", "detail": {}},
        "displayMessage": "Authenticate user via IDP",
        "legacyEventType": "core.user_auth.idp.saml.login_success",
        "securityContext": {
            "isp": "Easttel",
            "asOrg": "Easttel",
            "domain": "example.org",
            "isProxy": False,
            "asNumber": 3741,
        },
        "authenticationContext": {
            "issuer": None,
            "interface": "IDP Instance",
            "credentialType": "ASSERTION",
            "externalSessionId": "kjrgFtXuZnABQV9Vq1A2c",
            "authenticationStep": 0,
            "credentialProvider": None,
            "authenticationProvider": "FEDERATION",
        },
    }
    # flake8: qa


@pytest.fixture
def message2():
    # flake8: noqa
    return {
        "uuid": "cb9a43c9-a765-49ba-b2d5-7b9a263d4061",
        "actor": {
            "id": "eWiaLPtSTpjyy1BIwNFXg",
            "type": "User",
            "alternateId": "john.doe@example.org",
            "detailEntry": None,
            "displayName": "John Doe",
        },
        "client": {
            "id": None,
            "zone": "None",
            "device": "Computer",
            "ipAddress": "1.2.3.4",
            "userAgent": {
                "os": "Windows 10",
                "browser": "CHROME",
                "rawUserAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
            },
            "geographicalContext": {
                "city": "Paris",
                "state": "Ile-de-France",
                "country": "France",
                "postalCode": "75000",
                "geolocation": {"lat": 48.856944, "lon": 2.351389},
            },
        },
        "device": None,
        "target": [
            {
                "id": "eWiaLPtSTpjyy1BIwNFXg",
                "type": "User",
                "alternateId": "john.doe@example.org",
                "detailEntry": None,
                "displayName": "John Doe",
            },
            {
                "id": "kdYO9RZnIHNhV6vii333b",
                "type": "AuthenticatorEnrollment",
                "alternateId": "unknown",
                "detailEntry": {"methodTypeUsed": "Password", "methodUsedVerifiedProperties": "[USER_PRESENCE]"},
                "displayName": "Password",
            },
        ],
        "outcome": {"reason": None, "result": "SUCCESS"},
        "request": {
            "ipChain": [
                {
                    "ip": "1.2.3.4",
                    "source": None,
                    "version": "V4",
                    "geographicalContext": {
                        "city": "Paris",
                        "state": "Ile-de-France",
                        "country": "France",
                        "postalCode": None,
                        "geolocation": {"lat": 48.856944, "lon": 2.351389},
                    },
                }
            ]
        },
        "version": "0",
        "severity": "INFO",
        "eventType": "user.authentication.auth_via_mfa",
        "published": "2022-11-02T12:00:00.000Z",
        "transaction": {"id": "jI80snAs0ZMym5tvc8Jbp", "type": "WEB", "detail": {}},
        "displayMessage": "Authentication of user via MFA",
        "legacyEventType": "core.user.factor.attempt_success",
        "securityContext": {
            "isp": "Easttel",
            "asOrg": "Easttel",
            "domain": "example.org",
            "isProxy": False,
            "asNumber": 3741,
        },
        "authenticationContext": {
            "issuer": None,
            "interface": None,
            "credentialType": None,
            "externalSessionId": "kjrgFtXuZnABQV9Vq1A2c",
            "authenticationStep": 0,
            "credentialProvider": "OKTA_CREDENTIAL_PROVIDER",
            "authenticationProvider": "FACTOR_PROVIDER",
        },
    }
    # flake8: qa


def test_fetch_events(trigger, message1, message2):
    now = datetime.now(timezone.utc)
    recent_date = now - timedelta(seconds=34)

    messages = [
        {**message1, "published": recent_date.isoformat()},
        message2,
    ]

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get("https://tenant_id.okta.com/api/v1/logs", status_code=200, json=messages)
        events = trigger.fetch_events()
        initial_offset = trigger.cursor.offset

        assert list(events) == [messages]
        assert trigger.cursor.offset == initial_offset


def test_fetch_events_with_pagination(trigger, message1, message2):
    now = datetime.now(timezone.utc)
    recent_date = now - timedelta(seconds=45)

    response_1 = [
        {**message1, "published": recent_date.isoformat()},
    ]

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://tenant_id.okta.com/api/v1/logs",
            status_code=200,
            json=response_1,
            headers={"Link": "https://tenant_id.okta.com/api/v1/logs?after=1111111; rel=next"},
        )
        mock_requests.get("https://tenant_id.okta.com/api/v1/logs?after=1111111", status_code=200, json=[message2])
        events = trigger.fetch_events()
        initial_offset = trigger.cursor.offset

        assert list(events) == [response_1, [message2]]
        assert trigger.cursor.offset == initial_offset


def test_fetch_events_with_pagination_2(trigger, message1, message2):
    now = datetime.now(timezone.utc)
    expected_new_checkpoint_time = now - timedelta(seconds=10)

    result_message_1 = {
        **message1,
        "published": expected_new_checkpoint_time.isoformat(),
    }

    result_message_2 = {
        **message2,
        "published": (expected_new_checkpoint_time - timedelta(seconds=11)).isoformat(),
    }

    first_response = [{**result_message_1, "uuid": str(uuid.uuid4())} for _ in range(10)]
    second_response = [{**result_message_2, "uuid": str(uuid.uuid4())} for _ in range(5)]

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://tenant_id.okta.com/api/v1/logs",
            status_code=200,
            json=first_response + [result_message_1],
            headers={"Link": "https://tenant_id.okta.com/api/v1/logs?after=1111111; rel=next"},
        )

        mock_requests.get(
            "https://tenant_id.okta.com/api/v1/logs?after=1111111",
            status_code=200,
            json=second_response + [result_message_2],
        )

        # caching some of the uuids
        for event in first_response + second_response:
            trigger.events_cache[event["uuid"]] = True

        initial_offset = trigger.cursor.offset
        events = list(trigger.fetch_events())

        assert events == [[result_message_1], [result_message_2]]
        assert trigger.cursor.offset == initial_offset


def test_next_batch_updates_checkpoint_after_push(trigger, message1, message2):
    now = datetime.now(timezone.utc)
    recent_date = now - timedelta(seconds=20)
    messages = [
        {**message1, "published": recent_date.isoformat()},
        {**message2, "published": recent_date.isoformat()},
    ]

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get("https://tenant_id.okta.com/api/v1/logs", status_code=200, json=messages)
        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert trigger.cursor.offset.isoformat() == get_upper_second(recent_date).isoformat()


def test_next_batch_does_not_update_checkpoint_if_push_fails(trigger, message1):
    now = datetime.now(timezone.utc)
    recent_date = now - timedelta(seconds=20)
    message = {**message1, "published": recent_date.isoformat()}
    initial_offset = trigger.cursor.offset

    trigger.push_events_to_intakes = MagicMock(side_effect=RuntimeError("push failed"))

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get("https://tenant_id.okta.com/api/v1/logs", status_code=200, json=[message])

        with pytest.raises(RuntimeError, match="push failed"):
            trigger.next_batch()

        assert trigger.cursor.offset == initial_offset
        assert message["uuid"] not in trigger.events_cache


def test_next_batch_sleep_until_next_round(trigger, message1, message2):
    with patch("okta_modules.system_log_trigger.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://tenant_id.okta.com/api/v1/logs",
            status_code=200,
            json=[message1, message2],
        )
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 1


def test_long_next_batch_should_not_sleep(trigger, message1, message2):
    with patch("okta_modules.system_log_trigger.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://tenant_id.okta.com/api/v1/logs",
            status_code=200,
            json=[message1, message2],
        )
        batch_duration = trigger.configuration.frequency + 20  # the batch lasts more than the frequency
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 0

        events_cache = trigger.events_cache
        loaded_cache = trigger.load_events_cache()

        assert events_cache == loaded_cache
        assert events_cache[message1["uuid"]] == True
        assert events_cache[message2["uuid"]] == True


@pytest.mark.skipif("{'OKTA_BASE_URL', 'OKTA_API_TOKEN'}" ".issubset(os.environ.keys()) == False")
def test_run_integration(data_storage):
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    with patch("okta_modules.system_log_trigger.datetime") as mock_datetime:
        mock_datetime.now.return_value = one_hour_ago
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        module = OktaModule()
        trigger = SystemLogConnector(module=module, data_path=data_storage)
        # mock the log function of trigger that requires network access to the api for reporting
        trigger.log = MagicMock()
        trigger.log_exception = MagicMock()
        trigger.push_events_to_intakes = MagicMock()
        trigger.module.configuration = {
            "base_url": os.environ["OKTA_BASE_URL"],
            "apikey": os.environ["OKTA_API_TOKEN"],
        }
        trigger.configuration = {"intake_key": "0123456789", "ratelimit_per_minute": 10}
        main_thread = Thread(target=trigger.run)
        main_thread.start()

        # wait few seconds
        time.sleep(60)
        trigger._stop_event.set()
        main_thread.join(timeout=60)

        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls) > 0


def test_handle_response_error(data_storage):
    module = OktaModule()
    trigger = SystemLogConnector(module=module, data_path=data_storage)
    response = Response()
    response.status_code = 500
    response.reason = "Internal Error"
    with pytest.raises(FetchEventsException) as m:
        trigger._handle_response_error(response)

    assert str(m.value) == "Request on Okta API to fetch events failed with status 500 - Internal Error"


def test_default_cache_size_is_2000(trigger):
    """Test that cache size is set to the connector default."""
    assert trigger.cache_size == 2000, f"Cache size should be 2000, got {trigger.cache_size}"


def test_checksum_deduplication_without_uuid(trigger, message1):
    """Test that compute_event_checksum works for events without UUID."""
    event_without_uuid = {**message1, "uuid": None}

    # Verify checksum is computed consistently
    checksum1 = compute_event_checksum(event_without_uuid)
    checksum2 = compute_event_checksum(event_without_uuid)

    assert checksum1 == checksum2, "Checksum should be deterministic"
    assert isinstance(checksum1, str), "Checksum should be a string"
    assert len(checksum1) == 64, "Checksum should be a full SHA-256 hex digest"


def test_events_cache_persists_across_save_and_load(trigger):
    """Test that cache persists and survives across next_batch calls."""
    # Verify cache persistence mechanism works
    test_uuid = str(uuid.uuid4())
    trigger.events_cache[test_uuid] = True
    trigger.save_events_cache()

    # Create a fresh cache from stored context
    fresh_cache = trigger.load_events_cache()

    assert test_uuid in fresh_cache, "Cache should persist after save/load"
    assert len(fresh_cache) > 0, "Loaded cache should not be empty"


def test_compute_event_checksum_with_target_dict(message1):
    event = {**message1, "target": {"id": "target-dict-id"}}

    checksum = compute_event_checksum(event)

    assert isinstance(checksum, str)
    assert len(checksum) == 64


def test_exit_sets_stop_event_and_logs(trigger):
    trigger.exit(None, None)

    trigger.log.assert_called_once_with(message="Stopping OKTA system logs connector", level="info")
    assert trigger._stop_event.is_set()


def test_handle_response_error_with_api_details(data_storage):
    module = OktaModule()
    trigger = SystemLogConnector(module=module, data_path=data_storage)
    response = Response()
    response.status_code = 400
    response.reason = "Bad Request"
    response._content = b'{"errorCode":"E0000001","errorSummary":"Api validation failed"}'
    response.headers["Content-Type"] = "application/json"

    with pytest.raises(FetchEventsException) as exc_info:
        trigger._handle_response_error(response)

    assert "E0000001" in str(exc_info.value)
    assert "Api validation failed" in str(exc_info.value)


def test_fetch_events_with_filter_and_q_params(trigger, message1):
    trigger.configuration = {
        "intake_key": "intake_key",
        "filter": 'eventType eq "user.session.start"',
        "q": "mfa",
    }

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get("https://tenant_id.okta.com/api/v1/logs", status_code=200, json=[message1])

        events = list(trigger.fetch_events())

        assert events == [[message1]]
        assert len(mock_requests.request_history) == 1
        request = mock_requests.request_history[0]
        assert request.qs["filter"][0].lower() == 'eventtype eq "user.session.start"'
        assert request.qs["q"][0] == "mfa"


def test_fetch_events_empty_page_sleeps_when_all_events_filtered(trigger, message1):
    trigger.events_cache[message1["uuid"]] = True

    with patch("okta_modules.system_log_trigger.time.sleep") as mock_sleep, requests_mock.Mocker() as mock_requests:
        mock_requests.get("https://tenant_id.okta.com/api/v1/logs", status_code=200, json=[message1])

        assert list(trigger.fetch_events()) == []
        mock_sleep.assert_called_once_with(trigger.configuration.frequency)


def test_compute_batch_checkpoint_returns_none_when_missing_published(trigger):
    assert trigger._compute_batch_checkpoint([{"uuid": "without-published"}]) is None


def test_next_batch_caches_checksum_for_events_without_uuid(trigger, message1):
    event_without_uuid = {**message1, "uuid": None}
    checksum = compute_event_checksum(event_without_uuid)

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get("https://tenant_id.okta.com/api/v1/logs", status_code=200, json=[event_without_uuid])
        trigger.next_batch()

    assert checksum in trigger.events_cache


def test_next_batch_logs_no_events_when_empty_batch(trigger):
    trigger.fetch_events = MagicMock(return_value=iter([[]]))

    with patch("okta_modules.system_log_trigger.time.sleep"):
        trigger.next_batch()

    trigger.log.assert_any_call(message="No events to forward", level="info")


def test_run_logs_exception_and_continues(trigger):
    def failing_then_stop() -> None:
        if not hasattr(failing_then_stop, "called"):
            failing_then_stop.called = True  # type: ignore[attr-defined]
            raise RuntimeError("boom")

        trigger._stop_event.set()

    trigger.next_batch = MagicMock(side_effect=failing_then_stop)

    trigger.run()

    trigger.log_exception.assert_called_once()
