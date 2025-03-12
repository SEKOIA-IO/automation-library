import json
import gzip

import pytest
import requests_mock
from aioresponses import aioresponses

from mimecast_modules.helpers import download_batches


@pytest.fixture
def event_1():
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


def test_download_batches_synchronously(event_1):
    url = "https://storage.mydomain.com/path/object.gz"
    serialized_event = json.dumps(event_1)
    events = "\n".join([serialized_event] * 10)

    with requests_mock.Mocker() as mocked_requests:
        mocked_requests.get(url, content=gzip.compress(events.encode("utf-8")))

        assert download_batches([url] * 3, use_async=False) == [event_1] * 30


def test_download_batches_synchronously_empty_response(event_1):
    url = "https://storage.mydomain.com/path/object.gz"

    with requests_mock.Mocker() as mocked_requests:
        mocked_requests.get(url, content=gzip.compress(b''))

        assert download_batches([url], use_async=False) == []


def test_download_batches_asynchronously(event_1):
    url = "https://storage.mydomain.com/path/object.gz"
    serialized_event = json.dumps(event_1)
    events = "\n".join([serialized_event] * 10)

    with aioresponses() as mocked_requests:
        mocked_requests.get(url, body=gzip.compress(events.encode("utf-8")), repeat=4)

        assert download_batches([url] * 4, use_async=True) == [event_1] * 40


def test_download_batches_asynchronously_empty_response(event_1):
    url = "https://storage.mydomain.com/path/object.gz"

    with aioresponses() as mocked_requests:
        mocked_requests.get(url, body=gzip.compress(b''), repeat=2)

        assert download_batches([url] * 2, use_async=True) == []
