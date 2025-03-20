import asyncio
import json
import gzip
from collections.abc import Iterable
from datetime import datetime

import pytest
import requests_mock
from aioresponses import aioresponses

from mimecast_modules.helpers import AsyncGeneratorConverter, download_batches, batched, get_upper_second


def test_get_upper_second():
    starting_datetime = datetime(2022, 12, 11, 23, 45, 26, 208)
    expected_datetime = datetime(2022, 12, 11, 23, 45, 27)

    assert get_upper_second(starting_datetime) == expected_datetime


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

        assert list(download_batches([url] * 3)) == [event_1] * 30


def test_download_batches_synchronously_empty_response(event_1):
    url = "https://storage.mydomain.com/path/object.gz"

    with requests_mock.Mocker() as mocked_requests:
        mocked_requests.get(url, content=gzip.compress(b""))

        assert list(download_batches([url])) == []


def test_download_batches_asynchronously(event_1, event_loop):
    url = "https://storage.mydomain.com/path/object.gz"
    serialized_event = json.dumps(event_1)
    events = "\n".join([serialized_event] * 10)

    with aioresponses() as mocked_requests:
        mocked_requests.get(url, body=gzip.compress(events.encode("utf-8")), repeat=4)

        assert list(download_batches([url] * 4, loop=event_loop)) == [event_1] * 40


def test_download_batches_asynchronously_empty_response(event_1, event_loop):
    url = "https://storage.mydomain.com/path/object.gz"

    with aioresponses() as mocked_requests:
        mocked_requests.get(url, body=gzip.compress(b""), repeat=2)

        assert list(download_batches([url] * 2, loop=event_loop)) == []


@pytest.mark.parametrize(
    "iterable,nb_of_items,expected",
    [
        (
            "abcde",
            3,
            [
                ["a", "b", "c"],
                ["d", "e"],
            ],
        ),
        (
            "abcde",
            2,
            [
                ["a", "b"],
                ["c", "d"],
                ["e"],
            ],
        ),
        (
            ["aa", "bb", "cc", "dd", "ee"],
            2,
            [
                ["aa", "bb"],
                ["cc", "dd"],
                ["ee"],
            ],
        ),
    ],
)
def test_batched(iterable, nb_of_items, expected):
    assert list(batched(iterable, nb_of_items)) == expected


@pytest.mark.parametrize(
    "iterable,nb_of_items",
    [
        (
            ["aa", "bb", "cc", "dd", "ee"],
            0,
        ),
        (
            ["aa", "bb", "cc", "dd", "ee"],
            -1,
        ),
    ],
)
def test_batched_with_invalid_value(iterable, nb_of_items):
    with pytest.raises(ValueError):
        list(batched(iterable, nb_of_items))


def test_async_generator_converter(event_loop):
    async def async_generator():
        for i in range(100):
            yield i

    sync_generator = AsyncGeneratorConverter(async_generator(), event_loop)
    assert isinstance(sync_generator, Iterable)
    assert list(sync_generator) == list(range(100))


def test_async_generator_converter_empty_generator(event_loop):
    async def async_empty_generator():
        return
        yield

    sync_generator = AsyncGeneratorConverter(async_empty_generator(), event_loop)
    assert isinstance(sync_generator, Iterable)
    assert list(sync_generator) == []
