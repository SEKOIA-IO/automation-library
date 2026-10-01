from datetime import datetime, timedelta, timezone
from typing import cast
from unittest.mock import MagicMock, Mock, PropertyMock, call, patch

import pytest
import requests
import requests_mock
from dateutil.parser import isoparse
from pyrate_limiter import Duration, Limiter, RequestRate
from sekoia_automation.storage import PersistentJSON

from mimecast_modules import MimecastModule
from mimecast_modules.client import ApiClient
from mimecast_modules.client.auth import ApiKeyAuthentication
from mimecast_modules.connector_mimecast_siem import (
    MimecastSIEMConfiguration,
    MimecastSIEMConnector,
    MimecastSIEMWorker,
)
from mimecast_modules.models import MimecastModuleConfiguration


@pytest.fixture
def client_id():
    return "user123"


@pytest.fixture
def client_secret():
    return "some-secret"


@pytest.fixture
def rate_limiter():
    return Limiter(RequestRate(limit=50, interval=Duration.MINUTE * 15))


@pytest.fixture
def api_auth(client_id, client_secret, rate_limiter):
    return ApiKeyAuthentication(client_id, client_secret, rate_limiter)


@pytest.fixture
def api_client(api_auth, rate_limiter):
    return ApiClient(api_auth, rate_limiter, rate_limiter)


@pytest.fixture
def trigger(data_storage, client_id, client_secret):
    module = MimecastModule()
    module.configuration = cast(
        MimecastModuleConfiguration,
        {
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    trigger = MimecastSIEMConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = cast(
        MimecastSIEMConfiguration,
        {"intake_key": "intake_key", "frequency": 60},
    )
    yield trigger


@pytest.fixture
def batch_events_response_empty():
    return {"value": [], "@nextPage": "tokenNextPageLast==", "isCaughtUp": True}


@pytest.fixture
def batch_events_response_1():
    return {
        "value": [
            {
                "url": "https://s3-something.amazonaws.com/log1.json.gz",
                "size": 489,
                "expiry": "2024-06-05T11:50:06.389Z",
            }
        ],
        "isCaughtUp": False,
        "@nextPage": "tokenNextPage1=",
    }


@pytest.fixture
def batch_event_1():
    return {
        "aggregateId": "J5JwSy0HNvG7AvCg1sgDvQ_1715708284",
        "processingId": "hP5f7mBanAVkWJWfh4vYvca3zOi9I3jROBmH3Z_Kysk_1715708284",
        "accountId": "CDE22A102",
        "action": "Hld",
        "timestamp": 1715708287466,
        "senderEnvelope": "john.doe015@gmail.com",
        "messageId": "<CAF7=BmDb+6qHo+J5EB9oH+S4ncJOfEMsUYAEirX4MRZRJX+esw@mail.gmail.com>",
        "subject": "Moderate",
        "holdReason": "Spm",
        "totalSizeAttachments": "0",
        "numberAttachments": "0",
        "attachments": None,
        "emailSize": "3466",
        "type": "process",
        "subtype": "Hld",
        "_offset": 105825,
        "_partition": 137,
    }


def test_fetch_batches(trigger, batch_events_response_1, batch_events_response_empty, batch_event_1, api_client):
    with requests_mock.Mocker() as mock_requests, patch(
        "mimecast_modules.connector_mimecast_siem.download_batches"
    ) as mock_download_batches, patch("mimecast_modules.connector_mimecast_siem.time") as mock_time:
        mock_download_batches.side_effect = [[batch_event_1], []]

        mock_requests.post(
            "https://api.services.mimecast.com/oauth/token",
            json={
                "access_token": "foo-token",
                "token_type": "Bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.get(
            "https://api.services.mimecast.com/siem/v1/batch/events/cg",
            [{"json": batch_events_response_1}, {"json": batch_events_response_empty}],
        )

        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        consumer = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)
        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert consumer.cursor.offset == "tokenNextPageLast=="

        mock_time.sleep.assert_called_once_with(44)


def test_events_deduplication(
    trigger, batch_events_response_1, batch_events_response_empty, batch_event_1, api_client
):
    with requests_mock.Mocker() as mock_requests, patch(
        "mimecast_modules.connector_mimecast_siem.download_batches"
    ) as mock_download_batches, patch("mimecast_modules.connector_mimecast_siem.time") as mock_time:
        mock_download_batches.side_effect = [[batch_event_1], [batch_event_1], [batch_event_1], []]

        mock_requests.post(
            "https://api.services.mimecast.com/oauth/token",
            json={
                "access_token": "foo-token",
                "token_type": "Bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.get(
            "https://api.services.mimecast.com/siem/v1/batch/events/cg",
            [
                {"json": batch_events_response_1},
                {"json": batch_events_response_1},
                {"json": batch_events_response_1},
                {"json": batch_events_response_empty},
            ],
        )

        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        consumer = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)
        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert consumer.cursor.offset == "tokenNextPageLast=="

        mock_time.sleep.assert_called_once_with(44)


def test_start_consumers(trigger, api_client):
    with patch("mimecast_modules.connector_mimecast_siem.MimecastSIEMWorker.start") as mock_start:
        consumers = trigger.start_consumers(api_client)

        assert consumers is not None

        assert "process" in consumers
        assert "receipt" in consumers
        assert "journal" in consumers

        assert mock_start.called


def test_supervise_consumers(trigger, api_client):
    with patch("mimecast_modules.connector_mimecast_siem.MimecastSIEMWorker.start") as mock_start:
        consumers = {
            "a": Mock(**{"is_alive.return_value": False, "running": True}),
            "b": None,
            "c": Mock(**{"is_alive.return_value": True, "running": True}),
            "d": Mock(**{"is_alive.return_value": False, "running": False}),
        }

        trigger.supervise_consumers(consumers, api_client)
        assert mock_start.call_count == 2


def test_stop_consumers(trigger):
    consumers = {
        "a": Mock(**{"is_alive.return_value": False}),
        "b": None,
        "c": Mock(**{"is_alive.return_value": False}),
        "to_stop": Mock(**{"is_alive.return_value": True}),
    }
    trigger.stop_consumers(consumers)

    consumer_to_stop = consumers.get("to_stop")
    assert consumer_to_stop is not None
    assert consumer_to_stop.stop.called


def test_authentication_failed(
    trigger, batch_events_response_1, batch_events_response_empty, batch_event_1, api_client
):
    with requests_mock.Mocker() as mock_requests, patch(
        "mimecast_modules.connector_mimecast_siem.download_batches"
    ) as mock_download_batches, patch("mimecast_modules.connector_mimecast_siem.time") as mock_time:
        mock_download_batches.side_effect = [[batch_event_1], []]

        mock_requests.post(
            "https://api.services.mimecast.com/oauth/token",
            status_code=401,
            json={"fail": [{"code": "InvalidClientIdentifier", "message": "Client credentials are invalid"}]},
        )

        mock_requests.get(
            "https://api.services.mimecast.com/siem/v1/batch/events/cg",
            [{"json": batch_events_response_1}, {"json": batch_events_response_empty}],
        )

        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        consumer = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)
        with pytest.raises(requests.exceptions.HTTPError):
            consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 0
        assert trigger.log.mock_calls == [
            call(level="error", message="Authentication failed: Client credentials are invalid")
        ]


def test_permission_denied(trigger, batch_events_response_1, batch_events_response_empty, batch_event_1, api_client):
    with requests_mock.Mocker() as mock_requests, patch(
        "mimecast_modules.connector_mimecast_siem.download_batches"
    ) as mock_download_batches, patch("mimecast_modules.connector_mimecast_siem.time") as mock_time:
        mock_download_batches.side_effect = [[batch_event_1], []]

        mock_requests.post(
            "https://api.services.mimecast.com/oauth/token",
            json={
                "access_token": "foo-token",
                "token_type": "Bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.get(
            "https://api.services.mimecast.com/siem/v1/batch/events/cg",
            [
                {
                    "status_code": 403,
                    "json": {
                        "fail": [{"code": "app_forbidden", "message": "Forbidden to perform the requested operation"}]
                    },
                }
            ],
        )

        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        consumer = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)
        with pytest.raises(requests.exceptions.HTTPError):
            consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 0
        assert trigger.log.mock_calls == [
            call(level="error", message="Permission denied: Forbidden to perform the requested operation")
        ]


def test_temporary_unauthoried_for_url(
    trigger, batch_events_response_1, batch_events_response_empty, batch_event_1, api_client
):
    with requests_mock.Mocker() as mock_requests, patch(
        "mimecast_modules.connector_mimecast_siem.download_batches"
    ) as mock_download_batches, patch("mimecast_modules.connector_mimecast_siem.time") as mock_time:
        mock_download_batches.side_effect = [[batch_event_1], []]

        mock_requests.post(
            "https://api.services.mimecast.com/oauth/token",
            json={
                "access_token": "foo-token",
                "token_type": "Bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.get(
            "https://api.services.mimecast.com/siem/v1/batch/events/cg",
            [
                {
                    "status_code": 401,
                    "json": {
                        "fail": [{"code": "InvalidClientIdentifier", "message": "Client credentials are invalid"}]
                    },
                },
                {
                    "status_code": 200,
                    "json": batch_events_response_1,
                },
                {
                    "status_code": 200,
                    "json": batch_events_response_empty,
                },
            ],
        )

        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        consumer = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)
        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert consumer.cursor.offset == "tokenNextPageLast=="

        mock_time.sleep.assert_called_once_with(44)


def test_old_cursor(
    trigger, batch_events_response_1, batch_events_response_empty, batch_event_1, api_client, data_storage
):
    context = PersistentJSON("context.json", data_storage)

    # ensure that the cursor is None
    fake_date = datetime.now(timezone.utc) - timedelta(days=1)
    fake_date_str = fake_date.isoformat()
    fake_date_timestamp = int(fake_date.timestamp() * 1000.0)

    batch_event_1["timestamp"] = fake_date_timestamp + 1000

    with context as cache:
        cache["process"] = {"most_recent_date_seen": fake_date_str}

    with requests_mock.Mocker() as mock_requests, patch(
        "mimecast_modules.connector_mimecast_siem.download_batches"
    ) as mock_download_batches, patch("mimecast_modules.connector_mimecast_siem.time") as mock_time:
        mock_download_batches.side_effect = [[batch_event_1], []]

        mock_requests.post(
            "https://api.services.mimecast.com/oauth/token",
            json={
                "access_token": "foo-token",
                "token_type": "Bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.get(
            "https://api.services.mimecast.com/siem/v1/batch/events/cg",
            [{"json": batch_events_response_1}, {"json": batch_events_response_empty}],
        )

        batch_duration = 16  # the batch lasts 16 seconds
        start_time = fake_date_timestamp / 1000.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        consumer = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)
        assert consumer.old_cursor == fake_date

        consumer.next_batch()

        assert consumer.old_cursor is None
        assert consumer.cursor.offset == "tokenNextPageLast=="

        first_batch_request = next(
            item for item in mock_requests.request_history if "/siem/v1/batch/events/cg" in item.url
        )
        fake_date_ymd = fake_date.strftime("%Y-%m-%d")
        assert (
            first_batch_request.url == "https://api.services.mimecast.com/siem/v1/batch/events/cg?"
            f"pageSize=100&type=process&dateRangeStartsAt={fake_date_ymd}"
        )


def test_log_log_exception_and_stop_delegate(trigger, api_client):
    consumer = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)

    consumer.log(message="hello", level="info")
    consumer.log_exception(Exception("boom"), message="fail")
    assert consumer.running is True

    consumer.stop()

    trigger.log.assert_called_with(message="hello", level="info")
    trigger.log_exception.assert_called()
    assert consumer.running is False


def test_load_events_cache_and_save_events_cache(trigger, api_client):
    with trigger.context_lock:
        with PersistentJSON("cache.json", trigger.data_path) as context:
            context["process"] = {"events_cache": ["h1", "h2"]}

    consumer = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)
    assert "h1" in consumer.events_cache
    assert "h2" in consumer.events_cache

    consumer.events_cache["h3"] = True
    consumer.save_events_cache()

    with trigger.context_lock:
        with PersistentJSON("cache.json", trigger.data_path) as context:
            assert set(context["process"]["events_cache"]) == {"h1", "h2", "h3"}


def test_get_old_cursor_returns_none_when_older_than_7_days(trigger, api_client, data_storage):
    context = PersistentJSON("context.json", data_storage)
    old_date = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()

    with context as cache:
        cache["process"] = {"most_recent_date_seen": old_date}

    consumer = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)
    assert consumer.old_cursor is None


def test_build_fetch_params_uses_next_page_token(trigger, api_client):
    consumer = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)
    consumer.cursor.offset = "next-token"

    params = getattr(consumer, "_MimecastSIEMWorker__build_fetch_params")()

    assert params["nextPage"] == "next-token"
    assert params["type"] == "process"


def test_fetch_events_raises_value_error_without_http_response(trigger, api_client):
    consumer = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)

    with patch.object(
        consumer,
        "_MimecastSIEMWorker__fetch_next_events",
        side_effect=requests.exceptions.HTTPError(response=None),
    ):
        with pytest.raises(ValueError, match="Response does not contain any valid data"):
            list(consumer.fetch_events())


@pytest.mark.parametrize(
    "status_code,expected_message",
    [
        (401, "Authentication failed"),
        (403, "Permission denied"),
    ],
)
def test_fetch_events_logs_message_without_fail_details(trigger, api_client, status_code, expected_message):
    consumer = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)

    error = requests.exceptions.HTTPError()
    error.response = Mock(status_code=status_code)
    error.response.json.return_value = {"fail": []}

    with patch.object(consumer, "_MimecastSIEMWorker__fetch_next_events", side_effect=error):
        with pytest.raises(requests.exceptions.HTTPError):
            list(consumer.fetch_events())

    trigger.log.assert_called_with(message=expected_message, level="error")


def test_fetch_events_ignores_empty_event_batches(trigger, api_client):
    consumer = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)

    with patch.object(consumer, "_MimecastSIEMWorker__fetch_next_events", return_value=iter([[]])):
        assert list(consumer.fetch_events()) == []


def test_next_batch_logs_no_events_and_does_not_sleep_if_batch_is_long(trigger, api_client):
    consumer = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)

    with patch.object(consumer, "fetch_events", return_value=iter([])), patch(
        "mimecast_modules.connector_mimecast_siem.time"
    ) as mock_time:
        mock_time.time.side_effect = [0.0, 120.0, 121.0]
        consumer.next_batch()

    trigger.log.assert_any_call(message="process: No events to forward", level="info")
    assert mock_time.sleep.call_count == 0


def test_worker_run_handles_exception_then_stops(trigger, api_client):
    consumer = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)

    with patch.object(consumer, "next_batch", side_effect=Exception("boom")), patch.object(
        consumer, "save_events_cache"
    ) as save_events_cache, patch("mimecast_modules.connector_mimecast_siem.time.sleep") as sleep_mock, patch.object(
        MimecastSIEMWorker,
        "running",
        new_callable=PropertyMock,
        side_effect=[True, False],
    ):
        consumer.run()

    trigger.log_exception.assert_called_once()
    sleep_mock.assert_called_once_with(trigger.configuration.frequency)
    save_events_cache.assert_called_once()


def test_connector_data_path_property(trigger):
    assert trigger.data_path == trigger._data_path


def test_connector_run_initializes_clients_and_stops_consumers(trigger):
    trigger.module.configuration = cast(
        MimecastModuleConfiguration,
        {
            "client_id": "id",
            "client_secret": "secret",
        },
    )

    consumers = {"process": Mock()}
    with patch("mimecast_modules.connector_mimecast_siem.ApiKeyAuthentication") as api_auth_class, patch(
        "mimecast_modules.connector_mimecast_siem.ApiClient"
    ) as api_client_class, patch.object(
        trigger, "start_consumers", return_value=consumers
    ) as start_consumers, patch.object(
        trigger, "supervise_consumers"
    ) as supervise_consumers, patch.object(
        trigger, "stop_consumers"
    ) as stop_consumers, patch.object(
        MimecastSIEMConnector,
        "running",
        new_callable=PropertyMock,
        side_effect=[True, False],
    ), patch(
        "mimecast_modules.connector_mimecast_siem.time.sleep"
    ) as sleep_mock:
        trigger.run()

    api_auth_class.assert_called_once()
    api_client_class.assert_called_once()
    start_consumers.assert_called_once()
    supervise_consumers.assert_called_once()
    sleep_mock.assert_called_once_with(5)
    stop_consumers.assert_called_once_with(consumers)


def test_worker_can_disable_async_loop_with_empty_env(trigger, api_client, monkeypatch):
    monkeypatch.setenv("MIMECAST_ASYNC_DOWNLOAD", "")

    worker = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)

    assert worker._use_async is False
    assert worker._loop is None


def test_save_events_cache_creates_missing_log_type_entry(trigger, api_client):
    with trigger.context_lock:
        with PersistentJSON("cache.json", trigger.data_path) as context:
            context.clear()

    worker = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)
    worker.events_cache = {"new-hash": True}
    worker.save_events_cache()

    with trigger.context_lock:
        with PersistentJSON("cache.json", trigger.data_path) as context:
            assert context["process"]["events_cache"] == ["new-hash"]


def test_fetch_next_events_exits_immediately_when_worker_not_running(trigger, api_client):
    worker = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)
    fake_response = Mock(status_code=200)

    with patch.object(worker, "_MimecastSIEMWorker__build_fetch_params", return_value={}), patch.object(
        worker, "_MimecastSIEMWorker__get_next_batch_of_events", return_value=fake_response
    ), patch.object(MimecastSIEMWorker, "running", new_callable=PropertyMock, return_value=False):
        events = list(getattr(worker, "_MimecastSIEMWorker__fetch_next_events")())

    assert events == []


def test_fetch_events_keeps_previous_most_recent_timestamp(trigger, api_client):
    worker = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)
    newer = [{"timestamp": 2_000_000, "aggregateId": "a", "processingId": "b"}]
    older = [{"timestamp": 1_000_000, "aggregateId": "c", "processingId": "d"}]

    with patch.object(worker, "_MimecastSIEMWorker__fetch_next_events", return_value=iter([newer, older])):
        events = list(worker.fetch_events())

    assert events == [newer, older]


def test_next_batch_handles_empty_batch_inside_iteration(trigger, api_client):
    worker = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)

    with patch.object(worker, "fetch_events", return_value=iter([[]])), patch(
        "mimecast_modules.connector_mimecast_siem.time"
    ) as mock_time:
        mock_time.time.side_effect = [0.0, 2.0, 3.0]
        worker.next_batch()

    trigger.push_events_to_intakes.assert_not_called()


def test_fetch_events_handles_non_json_http_error_response(trigger, api_client):
    consumer = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)

    error = requests.exceptions.HTTPError()
    error.response = Mock(status_code=401, text="Gateway timeout")
    error.response.json.side_effect = ValueError("not json")

    with patch.object(consumer, "_MimecastSIEMWorker__fetch_next_events", side_effect=error):
        with pytest.raises(requests.exceptions.HTTPError):
            list(consumer.fetch_events())

    trigger.log.assert_called_with(message="Authentication failed: Gateway timeout", level="error")


def test_fetch_next_events_does_not_overwrite_existing_cursor_with_empty_next_page(trigger, api_client):
    consumer = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)
    consumer.cursor.offset = "existing-token"

    response = Mock(status_code=200)
    response.raise_for_status.return_value = None
    response.json.return_value = {"value": [], "isCaughtUp": True}

    with patch.object(consumer, "_MimecastSIEMWorker__build_fetch_params", return_value={}), patch.object(
        consumer, "_MimecastSIEMWorker__get_next_batch_of_events", return_value=response
    ), patch("mimecast_modules.connector_mimecast_siem.download_batches", return_value=iter(())), patch(
        "mimecast_modules.connector_mimecast_siem.batched", return_value=[]
    ):
        list(getattr(consumer, "_MimecastSIEMWorker__fetch_next_events")())

    assert consumer.cursor.offset == "existing-token"


@pytest.mark.parametrize(
    "json_value,text_value,expected",
    [
        ([{"message": "ignored"}], "", ""),
        ({"fail": "not-a-list"}, "", ""),
        ({"fail": []}, "upstream proxy html error", "upstream proxy html error"),
    ],
)
def test_extract_error_message_handles_unexpected_shapes(json_value, text_value, expected):
    response = Mock()
    response.json.return_value = json_value
    response.text = text_value

    extract_message = getattr(MimecastSIEMWorker, "_MimecastSIEMWorker__extract_error_message")
    message = extract_message(response)

    assert message == expected


def test_next_batch_logs_compact_summary_and_rate_limited_lag_warning(trigger, api_client):
    worker = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)
    worker._last_events_lag_seconds = 90_000
    events = [
        {"timestamp": 2_000_000, "aggregateId": "c", "processingId": "d"},
        {"timestamp": 1_000_000, "aggregateId": "a", "processingId": "b"},
        {"timestamp": 1_500_000, "aggregateId": "m", "processingId": "n"},
        {"timestamp": "invalid", "aggregateId": "x", "processingId": "y"},
    ]

    with patch.object(worker, "fetch_events", side_effect=[iter([events]), iter([events])]), patch(
        "mimecast_modules.connector_mimecast_siem.time"
    ) as mock_time, patch("mimecast_modules.connector_mimecast_siem.logger.info") as logger_info:
        mock_time.time.side_effect = [0.0, 2.0, 3.0, 5.0, 6.0, 8.0]

        worker.next_batch()
        worker.next_batch()

    summary_calls = [call for call in logger_info.call_args_list if call.args and call.args[0] == "Batch summary"]
    assert len(summary_calls) == 2
    assert (
        trigger.log.mock_calls.count(
            call(
                level="warning",
                message=(
                    "process: Event lag is high (90000s >= 86400s). " "Connector is likely catching up older events"
                ),
            )
        )
        == 1
    )


def test_get_next_batch_of_events_tracks_timeout_counters(trigger, api_client):
    worker = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)
    worker.client = Mock()
    worker.client.get.side_effect = requests.exceptions.ReadTimeout("timeout")

    with pytest.raises(requests.exceptions.ReadTimeout):
        getattr(worker, "_MimecastSIEMWorker__get_next_batch_of_events")("https://example.test", {})

    assert worker._batch_retry_count == 1
    assert worker._batch_timeout_count == 1


def test_get_next_batch_of_events_tracks_generic_timeout_counters(trigger, api_client):
    worker = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)
    worker.client = Mock()
    worker.client.get.side_effect = requests.exceptions.Timeout("timeout")

    with pytest.raises(requests.exceptions.Timeout):
        getattr(worker, "_MimecastSIEMWorker__get_next_batch_of_events")("https://example.test", {})

    assert worker._batch_retry_count == 1
    assert worker._batch_timeout_count == 1


def test_get_next_batch_of_events_counts_reauth_retry(trigger, api_client):
    worker = MimecastSIEMWorker(connector=trigger, log_type="process", client=api_client)

    unauthorized = Mock(status_code=401, reason="Unauthorized", text="")
    successful = Mock(status_code=200)

    worker.client = Mock()
    worker.client.get.side_effect = [unauthorized, successful]
    worker.client.auth = Mock()

    response = getattr(worker, "_MimecastSIEMWorker__get_next_batch_of_events")("https://example.test", {})

    assert response is successful
    assert worker.client.auth.get_credentials.call_count == 1
    assert worker._batch_retry_count == 1
