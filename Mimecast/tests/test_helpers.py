import asyncio
import json
import gzip
from collections.abc import Iterable
from datetime import datetime

import pytest
import requests_mock
from aioresponses import aioresponses

from mimecast_modules.helpers import AsyncGeneratorConverter, download_batches, batched, compute_hash_event


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


def test_compute_hash_event_0():
    event = {
        "processingId": "processingId",
        "aggregateId": "aggregateId",
        "sha1": "816b013c8be6e5708690645964b5d442c085041e",
        "eventType": "attachment protect",
    }
    expected_hash = "02eddf2a8696fee8"
    assert compute_hash_event(event) == expected_hash


def test_compute_hash_event_1():
    event = {
        "processingId": "processingId",
        "aggregateId": "aggregateId",
        "eventType": "av",
        "sha1": "816b013c8be6e5708690645964b5d442c085041e",
    }
    expected_hash = "574e5293b45f309c"
    assert compute_hash_event(event) == expected_hash


def test_compute_hash_event_2():
    event = {
        "processingId": "processingId",
        "aggregateId": "aggregateId",
        "messageId": "<11111111111111111111111111111111111111@mail.gmail.com>",
        "senderEnvelope": "john.doe@example.org",
        "recipients": "jane.doe@example.com",
        "type": "delivery",
    }
    expected_hash = "a35ffb02f9760e7b"
    assert compute_hash_event(event) == expected_hash


def test_compute_hash_event_3():
    event = {
        "processingId": "processingId",
        "aggregateId": "aggregateId",
        "senderEnvelope": "auser@mimecast.com",
        "messageId": "",
        "eventType": "impersonation protect",
        "recipients": "auser@mimecast.com",
    }
    expected_hash = "d11ab383ea2333e3"
    assert compute_hash_event(event) == expected_hash


def test_compute_hash_event_4():
    event = {
        "processingId": "processingId",
        "aggregateId": "aggregateId",
        "messageId": "<11111111111111111111111111111111111111@mail.gmail.com>",
        "senderEnvelope": "john.doe@example.org",
        "recipients": "jane.doe@example.com",
        "type": "internal email protect",
    }
    expected_hash = "0d63710a4d0f504c"
    assert compute_hash_event(event) == expected_hash


def test_compute_hash_event_5():
    event = {
        "aggregateId": "vC80NNxvOWKkBPnzSs04FA_1715699686",
        "processingId": "PGZfGuxEAu_kE-nGy1sjThBr5EYbm1ZcDKg-vXbRHLA_1715699686",
        "senderEnvelope": "newsletter@stub.com",
        "recipients": "neo@gmail.fr",
        "type": "journal",
    }
    expected_hash = "3746a53dd8723b0e"
    assert compute_hash_event(event) == expected_hash


def test_compute_hash_event_6():
    event = {
        "aggregateId": "J5JwSy0HNvG7AvCg1sgDvQ_1715708284",
        "processingId": "hP5f7mBanAVkWJWfh4vYvca3zOi9I3jROBmH3Z_Kysk_1715708284",
        "senderEnvelope": "john.doe015@gmail.com",
        "messageId": "<777777777777777777777777777777777777777777777777777@mail.gmail.com>",
        "type": "process",
    }
    expected_hash = "a6551d97df29ce95"
    assert compute_hash_event(event) == expected_hash


def test_compute_hash_event_7():
    event = {
        "processingId": "processingId",
        "aggregateId": "aggregateId",
        "senderEnvelope": "auser@mimecast.com",
        "messageId": "messageId",
        "eventType": "process",
    }
    expected_hash = "fe9d2e277f8a02e5"
    assert compute_hash_event(event) == expected_hash


def test_compute_hash_event_8():
    event = {
        "aggregateId": "aggId1",
        "processingId": "AAA_123",
        "senderEnvelope": "johndoe@gmail.com",
        "messageId": "1@mail.gmail.com>",
        "type": "process",
    }
    expected_hash = "3255b48e58585be1"
    assert compute_hash_event(event) == expected_hash


def test_compute_hash_event_9():
    event = {
        "aggregateId": "J5JwSy0HNvG7AvCg1sgDvQ_1715708284",
        "processingId": "hP5f7mBanAVkWJWfh4vYvca3zOi9I3jROBmH3Z_Kysk_1715708284",
        "senderEnvelope": "john.doe@gmail.com",
        "messageId": "<444444444444444444444444444444444444444444444444444@mail.gmail.com>",
        "recipients": "admin@example.org",
        "type": "receipt",
    }
    expected_hash = "beeba37b97f065c0"
    assert compute_hash_event(event) == expected_hash


def test_compute_hash_event_10():
    event = {
        "aggregateId": "YvXi4vUANvSwDaBxkq6SYA",
        "processingId": "RMkDQFp7L5gGaZ5jnsGVW4zLmvTVvWVb0lQeO9EBDRo_1736242544",
        "senderEnvelope": "john.doe@gmail.com",
        "messageId": "<111111111111111111111111111111111111111111111111111@mail.gmail.com>",
        "recipients": "admin@example.org",
        "type": "receipt",
    }
    expected_hash = "5e3912e39fc44867"
    assert compute_hash_event(event) == expected_hash


def test_compute_hash_event_11():
    event = {
        "processingId": "processingId",
        "aggregateId": "aggregateId",
        "messageId": "<11111111111111111111111111111111111111@mail.gmail.com>",
        "senderEnvelope": "john.doe@example.org",
        "recipients": "jane.doe@example.com",
        "type": "spam",
    }
    expected_hash = "d3121312806537c0"
    assert compute_hash_event(event) == expected_hash


def test_compute_hash_event_12():
    event = {
        "processingId": "req-aa8ae4a3334b30fbb07bbb9c2fb69048_1715766931",
        "aggregateId": "Y12X0yjKNr6A6yhIH48Wkw_1715766931",
        "senderEnvelope": "jeanne@gmail.com",
        "recipients": "john@example.org",
        "messageId": "<555555555555555555555555555555555555555555555555555@mail.gmail.com>",
        "type": "url protect",
    }
    expected_hash = "20245787bb2fc8f7"
    assert compute_hash_event(event) == expected_hash
