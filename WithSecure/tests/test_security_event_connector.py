import json
import os
import time
from datetime import UTC, datetime, timedelta
from signal import SIGINT
from threading import Thread
from unittest.mock import MagicMock

import pytest
import requests
import requests_mock

from withsecure import WithSecureModule
from withsecure.client.auth import API_AUTHENTICATION_URL
from withsecure.security_events_connector import API_SECURITY_EVENTS_URL, SecurityEventsConnector


@pytest.fixture
def message1():
    return {
        "severity": "info",
        "engine": "systemEventsLog",
        "serverTimestamp": (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "organization": {"name": "Test", "id": "00000000-0000-0000-0000-000000000000"},
        "action": "reported",
        "details": {
            "profileName": "DataGuard for server",
            "alertType": "system_events_log.event.info.added",
            "profileVersion": "1680195080",
            "systemDataEventId": "4625",
            "systemDataTimeCreated": "1680195137",
            "systemDataOpcode": "Info",
            "systemDataProviderName": "Microsoft-Windows-Security-Auditing",
            "description": "An account failed to log on.",
            "userName": "TEST\\domainadmin",
            "clientTimestamp": "1680195138628",
            "eventXml": (
                "<Event xmlns='http://schemas.microsoft.com/win/2004/08/events/event'><System>"
                "<Provider Name='Microsoft-Windows-Security-Auditing' Guid='{54849625-5478-4994-A5BA-3E3B0328C30D}'/>"
                "<EventID>4625</EventID><Version>0</Version><Level>0</Level><Task>12544</Task><Opcode>0</Opcode>"
                "<Keywords>0x8010000000000000</Keywords><TimeCreated SystemTime='2023-03-30T16:52:17.584737900Z'/>"
                "<EventRecordID>189743</EventRecordID><Correlation/><Execution ProcessID='500' ThreadID='2392'/>"
                "<Channel>Security</Channel><Computer>DC.KMTRGIHE.rds</Computer><Security/></System>"
                "<EventData><Data Name='SubjectUserSid'>S-1-0-0</Data><Data Name='SubjectUserName'>-</Data>"
                "<Data Name='SubjectDomainName'>-</Data><Data Name='SubjectLogonId'>0x0</Data>"
                "<Data Name='TargetUserSid'>S-1-0-0</Data><Data Name='TargetUserName'>WKS-10-UPDATED$</Data>"
                "<Data Name='TargetDomainName'>TEST</Data><Data Name='Status'>0xc000006d</Data>"
                "<Data Name='FailureReason'>%%2313</Data><Data Name='SubStatus'>0xc000006a</Data>"
                "<Data Name='LogonType'>3</Data><Data Name='LogonProcessName'>NtLmSsp </Data>"
                "<Data Name='AuthenticationPackageName'>NTLM</Data><Data Name='WorkstationName'>WKS-10-UPDATED</Data>"
                "<Data Name='TransmittedServices'>-</Data><Data Name='LmPackageName'>-</Data>"
                "<Data Name='KeyLength'>0</Data><Data Name='ProcessId'>0x0</Data><Data Name='ProcessName'>-</Data>"
                "<Data Name='IpAddress'>172.16.1.20</Data><Data Name='IpPort'>50059</Data></EventData></Event>"
            ),
            "throttledCount": "0",
            "systemDataComputer": "DC.TEST.rds",
            "profileId": "219659059",
            "systemDataRecordId": "189743",
            "hostIpAddress": "172.16.0.10/16",
            "systemDataProcessId": "500",
            "systemDataChannel": "Security",
            "systemDataLevel": "Information",
            "userPrincipalName": "domainadmin",
        },
        "persistenceTimestamp": (datetime(2023, 3, 30, 16, 52, 20, 354, tzinfo=UTC).isoformat()),
        "id": "6c85ad33-de08-3156-9354-e235ebf96b93_0",
        "device": {"name": "DC", "id": "00000000-0000-0000-0000-000000000000"},
        "clientTimestamp": "2023-03-30T16:52:18.628Z",
    }


@pytest.fixture
def message2():
    return {
        "severity": "info",
        "engine": "edr",
        "serverTimestamp": (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "organization": {"name": "Test", "id": "00000000-0000-0000-0000-000000000000"},
        "action": "closed",
        "details": {
            "incidentPublicId": "00000000-0000",
            "fingerprint": "e251d3b4ca26fc977452f271f18ed358909e3580",
            "initialDetectionTimestamp": "1680185665749",
            "risk": "HIGH",
            "categories": "SYSTEM_OR_TOOL_MISUSE",
            "incidentId": "00000000-0000-0000-0000-000000000000",
            "clientTimestamp": "1680185576000",
            "resolution": "CONFIRMED",
            "userSam": "TEST\\Frank",
        },
        "persistenceTimestamp": (datetime(2023, 3, 30, 14, 34, 5, 876, tzinfo=UTC).isoformat()),
        "id": "00000000-0000-0000-0000-000000000000_0",
        "device": {"name": "WKS-10-PLAIN", "id": "00000000-0000-0000-0000-000000000000"},
        "clientTimestamp": "2023-03-30T14:12:56Z",
    }


@pytest.fixture
def trigger(data_storage):
    def fake_log_cb(message: str, level: str):
        print(message)
        return None

    module = WithSecureModule()
    trigger = SecurityEventsConnector(module=module, data_path=data_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = fake_log_cb
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "client_id": "my-test-client-id",
        "secret": "my-secret",
    }
    trigger.configuration = {"intake_key": "test-intake-key", "frequency": 2}
    return trigger


@pytest.fixture
def trigger_with_preloaded_date(data_storage):
    def fake_log_cb(message: str, level: str):
        return None

    module = WithSecureModule()
    trigger = SecurityEventsConnector(module=module, data_path=data_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = fake_log_cb
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "client_id": "my-test-client-id",
        "secret": "my-secret",
    }
    trigger.configuration = {"intake_key": "test-intake-key", "frequency": 2}
    return trigger


def test_next_batch_with_single_page(trigger, message1, message2):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            API_AUTHENTICATION_URL,
            status_code=200,
            json={
                "access_token": "dummy-test-token",
                "token_type": "Bearer",
                "expires_in": 1799,
            },
        )
        mock_requests.post(
            API_SECURITY_EVENTS_URL,
            status_code=200,
            json={"items": [message1, message2]},
        )

        trigger.next_batch()
        assert len(trigger.push_events_to_intakes.mock_calls) == 1
        assert len(trigger.push_events_to_intakes.mock_calls[0][2]["events"]) == 2


def test_next_batch_is_empty(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            API_AUTHENTICATION_URL,
            status_code=200,
            json={
                "access_token": "dummy-test-token",
                "token_type": "Bearer",
                "expires_in": 1799,
            },
        )
        mock_requests.post(
            API_SECURITY_EVENTS_URL,
            status_code=200,
            json={"items": []},
        )

        trigger.next_batch()
        assert len(trigger.push_events_to_intakes.mock_calls) == 0


def test_next_batch_with_anchor(trigger, message1, message2):
    def custom_matcher(request: requests.PreparedRequest):
        if request.url == API_AUTHENTICATION_URL:
            resp = requests.Response()
            resp._content = json.dumps(
                {
                    "access_token": "dummy-test-token",
                    "token_type": "Bearer",
                    "expires_in": 1799,
                }
            ).encode()
            resp.status_code = 200

            return resp
        elif request.url.startswith(API_SECURITY_EVENTS_URL) and "anchor" not in request.body:
            resp = requests.Response()
            resp._content = json.dumps({"items": [message1], "nextAnchor": "next-anchor1"}).encode()
            resp.status_code = 200
            return resp
        elif request.url.startswith(API_SECURITY_EVENTS_URL) and "next-anchor1" in request.body:
            resp = requests.Response()
            resp._content = json.dumps({"items": [message2], "nextAnchor": "next-anchor2"}).encode()
            resp.status_code = 200
            return resp
        elif request.url.startswith(API_SECURITY_EVENTS_URL) and "next-anchor2" in request.body:
            resp = requests.Response()
            resp.status_code = 409
            return resp
        return None

    with requests_mock.Mocker() as mock_requests:
        mock_requests.add_matcher(custom_matcher)
        trigger.next_batch()
        assert len(trigger.push_events_to_intakes.mock_calls) == 2


def test_next_batch_with_anchor_and_issued_message_1(trigger, message1, message2):
    message_with_issue = {
        **message1,
        **{
            "organization": {
                "name": b"Syst\x00meTest".decode("latin-1"),
            }
        },
    }
    message_without_issue_2 = {
        **message2,
        **{
            "organization": {
                "name": b"Syst\xe8Test".decode("latin-1"),
            }
        },
    }

    def custom_matcher(request: requests.PreparedRequest):
        if request.url == API_AUTHENTICATION_URL:
            resp = requests.Response()
            resp._content = json.dumps(
                {
                    "access_token": "dummy-test-token",
                    "token_type": "Bearer",
                    "expires_in": 1799,
                }
            ).encode()
            resp.status_code = 200

            return resp
        elif request.url.startswith(API_SECURITY_EVENTS_URL) and "anchor" not in request.body:
            resp = requests.Response()
            resp._content = json.dumps({"items": [message_with_issue], "nextAnchor": "next-anchor1"}).encode()
            resp.status_code = 200
            return resp
        elif request.url.startswith(API_SECURITY_EVENTS_URL) and "next-anchor1" in request.body:
            resp = requests.Response()
            resp._content = json.dumps({"items": [message_without_issue_2], "nextAnchor": "next-anchor2"}).encode()
            resp.status_code = 200
            return resp
        elif request.url.startswith(API_SECURITY_EVENTS_URL) and "next-anchor2" in request.body:
            resp = requests.Response()
            resp.status_code = 409
            return resp
        return None

    with requests_mock.Mocker() as mock_requests:
        mock_requests.add_matcher(custom_matcher)
        trigger.next_batch()
        assert len(trigger.push_events_to_intakes.mock_calls) == 2


def test_fetch_next_events_raises_an_exception(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            API_AUTHENTICATION_URL,
            status_code=200,
            json={
                "access_token": "dummy-test-token",
                "token_type": "Bearer",
                "expires_in": 1799,
            },
        )
        mock_requests.post(API_SECURITY_EVENTS_URL, exc=requests.exceptions.ConnectTimeout)

        trigger.next_batch()


def test_run_is_interrupted_by_signal(trigger):
    pid = os.getpid()

    def set_stop_event():
        time.sleep(0.1)
        os.kill(pid, SIGINT)

    trigger.next_batch = MagicMock()
    Thread(target=set_stop_event, daemon=True).start()
    trigger.run()
    assert len(trigger.next_batch.mock_calls) > 0


def test_run_properly_handle_any_exception(trigger):
    pid = os.getpid()

    def set_stop_event():
        time.sleep(0.1)
        os.kill(pid, SIGINT)

    trigger.next_batch = MagicMock(side_effect=Exception("mocked error"))
    Thread(target=set_stop_event, daemon=True).start()
    trigger.run()
    assert len(trigger.next_batch.mock_calls) > 0


def test_load_recent_date_seen(trigger):
    with trigger.context as c:
        c["most_recent_date_seen"] = (datetime.now(UTC) - timedelta(days=3)).isoformat()

    assert trigger.most_recent_date_seen < datetime.now(UTC) - timedelta(days=3)


def test_most_recent_date_seen_is_capped_to_30_days(trigger):
    """A stored checkpoint older than 30 days must be capped to the API window."""
    with trigger.context as c:
        c["most_recent_date_seen"] = (datetime.now(UTC) - timedelta(days=45)).isoformat()

    most_recent_date_seen = trigger.most_recent_date_seen

    # capped to ~30 days ago (never older than the 30-day window)
    assert most_recent_date_seen >= datetime.now(UTC) - timedelta(days=30, seconds=5)


def test_cap_start_date_across_boundary(trigger):
    now = datetime.now(UTC)

    # within the window: unchanged
    recent = now - timedelta(days=10)
    assert trigger._cap_start_date(recent) == recent

    # beyond the window: capped to ~30 days ago
    stale = now - timedelta(days=60)
    capped = trigger._cap_start_date(stale)
    assert capped > stale
    assert capped >= now - timedelta(days=30, seconds=5)


def test_fetch_events_reapplies_cap_for_long_running_process(trigger, message1, message2):
    """
    Regression: an in-memory from_date older than 30 days (e.g. a long-running
    process without new events) must be re-capped before each request so the
    persistenceTimestamp range never exceeds 30 days.
    """
    # simulate a stale in-memory checkpoint set at startup 45 days ago
    trigger.from_date = datetime.now(UTC) - timedelta(days=45)

    captured_start: list[str] = []

    def custom_matcher(request: requests.PreparedRequest):
        resp = requests.Response()
        if request.url == API_AUTHENTICATION_URL:
            resp._content = json.dumps(
                {"access_token": "dummy-test-token", "token_type": "Bearer", "expires_in": 1799}
            ).encode()
            resp.status_code = 200
            return resp
        elif request.url.startswith(API_SECURITY_EVENTS_URL):
            for key, value in (pair.split("=", 1) for pair in request.body.split("&")):
                if key == "persistenceTimestampStart":
                    captured_start.append(value)
            resp._content = json.dumps({"items": [message1, message2]}).encode()
            resp.status_code = 200
            return resp
        return None

    with requests_mock.Mocker() as mock_requests:
        mock_requests.add_matcher(custom_matcher)
        trigger.next_batch()

    assert captured_start
    from urllib.parse import unquote

    start_date = datetime.fromisoformat(unquote(captured_start[0]))
    assert start_date >= datetime.now(UTC) - timedelta(days=30, seconds=5)


def test_next_batch_with_form_urlencoded_format(trigger, message1, message2):
    """Test that engineGroup parameters are correctly repeated in form-urlencoded format"""

    def custom_matcher(request: requests.PreparedRequest):
        if request.url == API_AUTHENTICATION_URL:
            resp = requests.Response()
            resp._content = json.dumps(
                {
                    "access_token": "dummy-test-token",
                    "token_type": "Bearer",
                    "expires_in": 1799,
                }
            ).encode()
            resp.status_code = 200
            return resp
        elif request.url.startswith(API_SECURITY_EVENTS_URL):
            # Verify that engineGroup is repeated in the request body
            assert "engineGroup=epp" in request.body
            assert "engineGroup=edr" in request.body
            assert "engineGroup=ecp" in request.body
            assert "Content-Type" in request.headers
            assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"

            resp = requests.Response()
            resp._content = json.dumps({"items": [message1, message2]}).encode()
            resp.status_code = 200
            return resp
        return None

    with requests_mock.Mocker() as mock_requests:
        mock_requests.add_matcher(custom_matcher)
        trigger.next_batch()
        assert len(trigger.push_events_to_intakes.mock_calls) == 1
        assert len(trigger.push_events_to_intakes.mock_calls[0][2]["events"]) == 2
