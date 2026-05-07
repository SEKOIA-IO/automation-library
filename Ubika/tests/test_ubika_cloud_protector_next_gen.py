import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest
from cachetools import LRUCache
from respx import MockRouter

from ubika_modules import UbikaModule
from ubika_modules.client.auth import AuthorizationError, AuthorizationTimeoutError
from ubika_modules.connector_ubika_cloud_protector_next_gen import UbikaCloudProtectorNextGenConnector
from ubika_modules.timestepper import TimeStepper


@pytest.fixture
def trigger(data_storage):
    module = UbikaModule()
    trigger = UbikaCloudProtectorNextGenConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = {
        "namespace": "sekoia",
        "refresh_token": "some_token_here",
        "intake_key": "intake_key",
        "frequency": 60,
        "chunk_size": 100,
        "timedelta": 5,
        "start_time": 1,
    }
    yield trigger


@pytest.fixture
def message1():
    return {
        "apiVersion": "logs.ubika.io/v1beta",
        "kind": "SecurityEvents",
        "metadata": {"name": "", "namespace": "", "created": None, "updated": None, "version": "0"},
        "spec": {
            "items": [
                {
                    "logAlertUid": "098f6bcd4621d373cade4e832627b4f6",
                    "timestamp": "1747326567848",
                    "request": {
                        "uid": "abcdef",
                        "body": "",
                        "hostname": "ubika.integration.sekoia.cloud",
                        "method": "GET",
                        "path": "/api/.env",
                        "headers": [
                            {"key": "x-request-id", "value": "4d1c331e-14af-4ce1-97a8-99c495ff6b18"},
                            {"key": "x-real-ip", "value": "176.98.186.48"},
                            {"key": "x-ubika-data", "value": "1"},
                            {"key": "host", "value": "ubika.integration.sekoia.cloud"},
                            {"key": "accept", "value": "*/*"},
                            {"key": "accept-encoding", "value": "gzip, deflate"},
                            {
                                "key": "user-agent",
                                "value": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
                            },
                        ],
                        "cookies": [],
                        "ipSource": "1.2.3.4",
                        "query": "",
                    },
                    "context": {"assetName": "testAsset", "assetNamespace": "sekoia", "reaction": "BLOCKED"},
                    "uid": "5a105e8b9d40e1329780d62ea2265d8a",
                    "tokens": {
                        "openapi3Name": "",
                        "openapi3Uid": "",
                        "openapi3ErrorType": "",
                        "openapi3ErrorDetails": "",
                        "part": "Multiple",
                        "reason": "ICX Engine: Path Traversal in Path",
                        "customMessage": "",
                        "engineUid": "icxEngine",
                        "engineName": "ICX Engine",
                        "matchingParts": [
                            {
                                "part": "Path",
                                "partKey": "",
                                "partKeyOperator": "",
                                "partKeyPattern": "",
                                "partKeyPatternUid": "",
                                "partKeyPatternName": "",
                                "partKeyPatternVersion": "",
                                "partKeyMatch": "",
                                "partValue": "/api/.env",
                                "partValuePattern": "",
                                "partValueOperator": "pattern",
                                "partValuePatternUid": "PathTraversalOnUriProprietaryPattern_PToU-00740-3.45.1",
                                "partValuePatternName": "Path transversal on URI",
                                "partValuePatternVersion": "PToU-00740-3.45.1",
                                "partValueMatch": "/.env",
                                "scoringlistRuleId": "",
                                "scoringlistRuleWeight": 0,
                            }
                        ],
                        "attackFamily": "Path Traversal",
                        "icxPolicyUid": "default_3.47.0",
                        "icxRuleName": "Path transversal",
                        "icxRuleUid": "abcdef12345",
                        "websocketOpcode": "",
                        "websocketFrom": "",
                        "canonSearchType": "",
                        "eaPolicyUid": "",
                        "eaPolicyName": "",
                        "eaStaticPolicyUid": "",
                        "eaRuleId": "",
                        "eaRuleName": "",
                        "eaTotalScore": 0,
                    },
                }
            ],
            "nextPageToken": "token123",
        },
    }


@pytest.fixture
def message2():
    return {
        "apiVersion": "logs.ubika.io/v1beta",
        "kind": "SecurityEvents",
        "metadata": {"name": "", "namespace": "", "created": None, "updated": None, "version": "0"},
        "spec": {"items": [], "nextPageToken": "tokenEnd"},
    }


@pytest.mark.respx(base_url="https://login.ubika.io")
def test_fetch_events_with_pagination(respx_mock: MockRouter, trigger, message1, message2):
    respx_mock.post("/auth/realms/main/protocol/openid-connect/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )
    )

    respx_mock.get(
        "https://api.ubika.io/rest/logs.ubika.io/v1/ns/sekoia/security-events",
        params={
            "filters.fromDate": "1747326567845",
            "filters.toDate": "1747326667845",
            "pagination.realtime": "true",
            "pagination.pageSize": "100",
        },
    ).mock(return_value=httpx.Response(200, json=message1))

    respx_mock.get(
        "https://api.ubika.io/rest/logs.ubika.io/v1/ns/sekoia/security-events",
        params={
            "pagination.pageToken": "token123",
            "pagination.pageSize": "100",
            "pagination.realtime": "true",
        },
    ).mock(return_value=httpx.Response(200, json=message2))

    trigger.from_timestamp = 1747326567845
    events = trigger._get_pages(
        endpoint="security-events",
        params={
            "filters.fromDate": 1747326567845,
            "filters.toDate": 1747326667845,
            "pagination.realtime": True,
            "pagination.pageSize": 100,
        },
    )

    assert list(events) == [message1["spec"]["items"]]


@pytest.mark.respx(base_url="https://login.ubika.io")
def test_next_batch_sleep_until_next_round(respx_mock: MockRouter, trigger, message1, message2, sleep_spy):
    respx_mock.post("/auth/realms/main/protocol/openid-connect/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )
    )

    start = datetime.fromtimestamp(1747326560, tz=timezone.utc)
    end = datetime.fromtimestamp(1747326660, tz=timezone.utc)

    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    respx_mock.get(
        "https://api.ubika.io/rest/logs.ubika.io/v1/ns/sekoia/security-events",
        params={
            "filters.fromDate": str(start_ms),
            "filters.toDate": str(end_ms),
            "pagination.realtime": "true",
            "pagination.pageSize": "100",
        },
    ).mock(return_value=httpx.Response(200, json=message1))

    respx_mock.get(
        "https://api.ubika.io/rest/logs.ubika.io/v1/ns/sekoia/security-events",
        params={
            "pagination.pageToken": "token123",
            "pagination.pageSize": "100",
            "pagination.realtime": "true",
        },
    ).mock(return_value=httpx.Response(200, json=message2))

    batch_duration = trigger.configuration.frequency + 20
    start_time = 1747326560
    end_time = start_time + batch_duration
    sleep_spy.time.side_effect = [start_time, end_time, end_time]

    trigger.next_batch(start, end)

    assert trigger.push_events_to_intakes.call_count == 1
    assert sleep_spy.sleep.call_count == 0


@pytest.mark.respx(base_url="https://login.ubika.io")
def test_authorization_http_error_without_retry(respx_mock: MockRouter, trigger):
    route = respx_mock.post("/auth/realms/main/protocol/openid-connect/token")
    route.mock(
        return_value=httpx.Response(
            400,
            json={"error": "invalid_grant", "error_description": "Invalid refresh token"},
        )
    )

    start = datetime.fromtimestamp(1747326560, tz=timezone.utc)
    end = datetime.fromtimestamp(1747326660, tz=timezone.utc)

    with pytest.raises(AuthorizationError):
        trigger.next_batch(start=start, end=end)

    assert route.call_count == 1


@pytest.mark.respx(base_url="https://login.ubika.io")
def test_authorization_http_error_with_retry(respx_mock: MockRouter, trigger):
    route = respx_mock.post("/auth/realms/main/protocol/openid-connect/token")
    route.mock(
        return_value=httpx.Response(
            500,
            json={"error": "some_error", "error_description": "Error worth retrying"},
        )
    )

    start = datetime.fromtimestamp(1747326560, tz=timezone.utc)
    end = datetime.fromtimestamp(1747326660, tz=timezone.utc)

    with pytest.raises(AuthorizationError):
        trigger.next_batch(start=start, end=end)

    assert route.call_count == 5


@pytest.mark.respx(base_url="https://login.ubika.io")
def test_authorization_timeout_error(respx_mock: MockRouter, trigger):
    route = respx_mock.post("/auth/realms/main/protocol/openid-connect/token")
    route.side_effect = httpx.TimeoutException("Timeout")

    start = datetime.fromtimestamp(1747326560, tz=timezone.utc)
    end = datetime.fromtimestamp(1747326660, tz=timezone.utc)

    with pytest.raises(AuthorizationTimeoutError):
        trigger.next_batch(start=start, end=end)

    assert route.call_count == 5


def test_stepper_initializes_with_backfill(monkeypatch, trigger):
    """
    If no checkpoint in context, stepper should call TimeStepper.create(...)
    with the configured start_time hours back.
    """
    # Override some configuration parameters for the test
    trigger.configuration.start_time = 2
    # Make context.json empty
    with trigger.context as c:
        c.clear()

    # Intercept create(...)
    sentinel = object()
    called = {}

    def fake_create(self, freq, delta, start_h):
        called["args"] = (freq, delta, start_h)
        return sentinel

    monkeypatch.setattr(TimeStepper, "create", fake_create)

    # Access the cached property
    stepper = trigger.stepper

    # It must be our sentinel, and args match your config
    assert stepper is sentinel
    assert called["args"] == (
        trigger.configuration.frequency,
        trigger.configuration.timedelta,
        trigger.configuration.start_time,
    )


def test_stepper_clamps_dates_older_than_one_month(monkeypatch, trigger):
    # Override some configuration parameters for the test
    trigger.configuration.frequency = 42
    old_dt = datetime.now(timezone.utc) - timedelta(days=60)
    with trigger.context as cache:
        cache["most_recent_date_seen"] = old_dt.isoformat()

    # Monkey‐patch create_from_time to capture args and return sentinel
    sentinel = object()
    called = {}

    def fake_create_from_time(self, date_arg, freq_arg, delta_arg):
        called["date"], called["freq"], called["delta"] = (date_arg, freq_arg, delta_arg)
        return sentinel

    monkeypatch.setattr(TimeStepper, "create_from_time", fake_create_from_time)

    # Access the cached property
    stepper = trigger.stepper

    # It must have returned our sentinel
    assert stepper is sentinel

    # And the date passed in was clamped to one_month_ago
    now = datetime.now(timezone.utc)
    one_month_ago = now - timedelta(days=30)
    passed = called["date"]
    # allow 2s slack for test timing
    assert abs((passed - one_month_ago).total_seconds()) < 2

    # And create_from_time got the right config args
    assert called["freq"] == trigger.configuration.frequency
    assert called["delta"] == trigger.configuration.timedelta


def test_load_events_cache_and_filter(trigger):
    """
    load_events_cache should read the list of hashes from cache.json,
    dedupe them into an in-memory cache, and filter_processed_events
    should skip already-seen IDs.
    """
    # Seed the persisted cache list with duplicates
    with trigger.cache_context as cache:
        cache["events_cache"] = ["h1", "h2", "h1"]

    # Call load_events_cache() and verify deduplication
    loaded_cache: LRUCache = trigger.load_events_cache()
    # keys of loaded cache must be exactly {"h1","h2"}
    assert set(loaded_cache.keys()) == {"h1", "h2"}

    # Give the connector that deduped cache
    trigger.events_cache = loaded_cache

    # Now test filter_processed_events
    # If we send events with h1 (already seen) and h3 (new),
    # only the h3 event should pass through.
    events = [{"logAlertUid": "h1"}, {"logAlertUid": "h3"}]
    filtered = trigger.filter_processed_events(events)
    assert filtered == [{"logAlertUid": "h3"}]


def test_run_stops_immediately_if_stop_event_set(monkeypatch, trigger):
    """
    If _stop_event.is_set() is True at the start, run() must break
    out of the loop without calling next_batch.
    """
    # Stub the stepper to yield some windows (they will never run)
    fake_windows = [(datetime.now(timezone.utc), datetime.now(timezone.utc))]
    trigger.stepper = MagicMock(ranges=MagicMock(return_value=fake_windows))

    # Spy on next_batch
    trigger.next_batch = MagicMock()

    # Make stop_event return True immediately
    trigger._stop_event.is_set = MagicMock(return_value=True)

    # Prevent any real sleep
    monkeypatch.setattr("time.sleep", lambda s: None)

    # Call run()
    trigger.run()

    # next_batch should never have been called
    assert trigger.next_batch.call_count == 0


def test_run_breaks_on_next_batch_exception(monkeypatch, trigger):
    """
    If next_batch raises, run() should catch it, call log_exception once,
    and break the loop (no second call).
    """
    # Prepare 2 windows (second should never run)
    now = datetime.now(timezone.utc)
    w1 = (now, now + timedelta(minutes=1))
    w2 = (w1[1], w1[1] + timedelta(minutes=1))
    trigger.stepper = MagicMock(ranges=MagicMock(return_value=[w1, w2]))

    # Stub next_batch to throw on first call
    exc = RuntimeError("boom")
    trigger.next_batch = MagicMock(side_effect=exc)

    # Spy on log_exception
    trigger.log_exception = MagicMock()

    # Run
    trigger.run()

    # next_batch should have been called exactly once
    trigger.next_batch.assert_called_once_with(*w1)
    # log_exception should have been called once with our exception
    trigger.log_exception.assert_called_once()
    args, kwargs = trigger.log_exception.call_args
    assert args[0] is exc
    assert kwargs.get("message") == "Failed to forward events"
