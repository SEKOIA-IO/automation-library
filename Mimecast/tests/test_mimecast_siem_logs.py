from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, call, patch

import pytest
import requests
import requests_mock
from dateutil.parser import isoparse
from pyrate_limiter import Duration, Limiter, RequestRate
from sekoia_automation.storage import PersistentJSON

from mimecast_modules import MimecastModule
from mimecast_modules.client import ApiClient
from mimecast_modules.client.auth import ApiKeyAuthentication
from mimecast_modules.connector_mimecast_siem import MimecastSIEMConnector, MimecastSIEMWorker


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
    module.configuration = {
        "client_id": client_id,
        "client_secret": client_secret,
    }
    trigger = MimecastSIEMConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = {"intake_key": "intake_key", "frequency": 60}
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
