import os
import time
from datetime import datetime, timedelta, timezone
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest
import requests_mock
from requests import Response

from okta_modules import OktaModule
from okta_modules.system_log_trigger import FetchEventsException, SystemLogConnector


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
    messages = [message1, message2]
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get("https://tenant_id.okta.com/api/v1/logs", status_code=200, json=messages)
        events = trigger.fetch_events()

        assert list(events) == [messages]
        assert trigger.from_date.isoformat() == "2022-11-15T08:04:23+00:00"


def test_fetch_events_with_pagination(trigger, message1, message2):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://tenant_id.okta.com/api/v1/logs",
            status_code=200,
            json=[message1],
            headers={"Link": "https://tenant_id.okta.com/api/v1/logs?after=1111111; rel=next"},
        )
        mock_requests.get("https://tenant_id.okta.com/api/v1/logs?after=1111111", status_code=200, json=[message2])
        events = trigger.fetch_events()

        assert list(events) == [[message1], [message2]]
        assert trigger.from_date.isoformat() == "2022-11-15T08:04:23+00:00"


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
