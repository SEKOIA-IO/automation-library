from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests_mock

from mimecast_modules import MimecastModule
from mimecast_modules.connector_mimecast_siem import MimecastSIEMConnector, MimecastSIEMWorker


@pytest.fixture
def fake_time():
    yield datetime(2024, 5, 1, 11, 59, 59, tzinfo=timezone.utc)


@pytest.fixture
def patch_datetime_now(fake_time):
    with patch("mimecast_modules.connector_mimecast_siem.datetime") as mock_datetime:
        mock_datetime.now.return_value = fake_time
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        mock_datetime.fromtimestamp = lambda ts: datetime.fromtimestamp(ts)
        yield mock_datetime


@pytest.fixture
def trigger(data_storage):
    module = MimecastModule()

    trigger = MimecastSIEMConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "client_id": "user123",
        "client_secret": "some-secret",
    }
    trigger.configuration = {"intake_key": "intake_key", "frequency": 60}
    yield trigger


@pytest.fixture
def batch_events_response_empty():
    return {"value": [], "@nextPage": "tokenNextPageLast=="}


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


@pytest.fixture
def stream_events_response_empty():
    return {"value": [], "@nextLink": "tokenNextPageLast==", "@nextPage": "tokenNextPageLast==", "pageSize": 0}


@pytest.fixture
def stream_events_response_1():
    return {
        "value": [
            {
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
        ],
        "@nextLink": "tokenNextPage==",
        "@nextPage": "tokenNextPage==",
        "pageSize": 1,
    }


def test_fetch_batches(
    trigger, patch_datetime_now, batch_events_response_1, batch_events_response_empty, batch_event_1
):
    with requests_mock.Mocker() as mock_requests, patch(
        "mimecast_modules.connector_mimecast_siem.MimecastSIEMWorker.download_batches"
    ) as mock_download_batches, patch("mimecast_modules.connector_mimecast_siem.time") as mock_time:
        mock_download_batches.side_effect = [[batch_event_1], []]

        mock_requests.post(
            f"https://api.services.mimecast.com/oauth/token",
            json={
                "access_token": "foo-token",
                "token_type": "Bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.get(
            f"https://api.services.mimecast.com/siem/v1/batch/events/cg",
            [{"json": batch_events_response_1}, {"json": batch_events_response_empty}],
        )

        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        consumer = MimecastSIEMWorker(connector=trigger, log_type="process")
        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        mock_time.sleep.assert_called_once_with(44)
