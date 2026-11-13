"""Tests related to connector."""

import gzip
from copy import copy
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import orjson
import pytest
from azure.storage.blob import BlobProperties
from sekoia_automation.module import Module

from connectors.blob import AzureBlobConnectorConfig, azure_blob
from connectors.blob.azure_blob import AzureBlobConnector


@pytest.fixture
def pushed_events_ids(session_faker) -> list[str]:
    """
    Generate random list of events ids.

    Args:
        session_faker: Faker

    Returns:
        list[str]:
    """
    return [session_faker.word() for _ in range(session_faker.random.randint(1, 10))]


@pytest.fixture
def connector(
    symphony_storage,
    container_name,
    account_name,
    account_key,
    mock_push_data_to_intakes,
    session_faker,
):
    module = Module()

    config = AzureBlobConnectorConfig(
        intake_key=session_faker.word(),
        container_name=container_name,
        account_name=account_name,
        account_key=account_key,
    )

    trigger = AzureBlobConnector(
        module=module,
        data_path=symphony_storage,
    )

    # Mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()

    trigger.push_data_to_intakes = mock_push_data_to_intakes

    trigger.configuration = config

    return trigger


@pytest.mark.asyncio
async def test_azure_blob_connector_last_event_date(connector):
    """
    Test `last_event_date`.

    Args:
        connector: AzureBlobConnector
    """
    with connector.context as cache:
        cache["last_event_date"] = None

    current_date = datetime.now(timezone.utc).replace(microsecond=0)
    one_hour_ago = current_date - timedelta(hours=1)

    assert connector.last_event_date == one_hour_ago

    with connector.context as cache:
        cache["last_event_date"] = current_date.isoformat()

    assert connector.last_event_date == current_date

    with connector.context as cache:
        cache["last_event_date"] = (one_hour_ago - timedelta(minutes=20)).isoformat()

    assert connector.last_event_date == one_hour_ago


class FakeBlobStorage:
    """In-memory blob storage serving byte ranges, like Azure Blob Storage."""

    def __init__(self) -> None:
        self.blobs: dict[str, BlobProperties] = {}
        self.contents: dict[str, bytes] = {}
        self.downloads: list[tuple[str, int, int]] = []

    def write(
        self, name: str, content: bytes, modified_at: datetime | None = None, created_at: datetime | None = None
    ):
        properties = self.blobs.get(name) or BlobProperties()
        properties.name = name
        properties.size = len(content)
        properties.last_modified = modified_at or datetime.now(timezone.utc)
        properties.creation_time = created_at or properties.creation_time or properties.last_modified
        self.blobs[name] = properties
        self.contents[name] = content

    def append(self, name: str, content: bytes, modified_at: datetime | None = None):
        self.write(name, self.contents[name] + content, modified_at=modified_at)

    def list_blobs(self):
        mock_list_blobs = MagicMock()
        mock_list_blobs.__aiter__.return_value = [copy(blob) for blob in self.blobs.values()]
        return mock_list_blobs

    async def download_blob_range(self, blob_name: str, offset: int, length: int) -> bytes:
        self.downloads.append((blob_name, offset, length))
        content = self.contents[blob_name]
        if offset >= len(content):
            raise ValueError("InvalidRange")

        return content[offset : offset + length]


def gzip_lines(*lines: bytes) -> bytes:
    return gzip.compress(b"".join(line + b"\n" for line in lines))


def make_lines(count: int, start: int = 0) -> list[bytes]:
    return [orjson.dumps({"id": index, "message": "event"}) for index in range(start, start + count)]


@pytest.fixture
def storage(connector) -> FakeBlobStorage:
    fake_storage = FakeBlobStorage()
    connector._azure_blob_storage_wrapper = fake_storage

    with connector.context as cache:
        cache["last_event_date"] = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()

    return fake_storage


def pushed_events(connector) -> list[str]:
    return [event for call in connector.push_data_to_intakes.call_args_list for event in call.kwargs["events"]]


@pytest.mark.asyncio
async def test_azure_blob_get_azure_blob_data_1(connector: AzureBlobConnector, storage, blob_content):
    """A plain blob with a single JSON document without trailing newline is forwarded."""
    storage.write("blob.json", blob_content)

    result = await connector.get_azure_blob_data()

    assert result == [blob_content.decode("utf-8")]


@pytest.mark.asyncio
async def test_azure_blob_get_azure_blob_data_2(connector: AzureBlobConnector, storage, blob_content):
    """Empty lines are ignored."""
    storage.write("blob.json", blob_content + b"\n\n\n" + blob_content + b"\n")

    result = await connector.get_azure_blob_data()

    assert result == [blob_content.decode("utf-8")] * 2


@pytest.mark.asyncio
async def test_azure_blob_get_azure_blob_data_3(connector: AzureBlobConnector, storage, blob_content):
    """A gzip blob is decompressed."""
    storage.write("blob.json.gz", gzip.compress(blob_content))

    result = await connector.get_azure_blob_data()

    assert result == [blob_content.decode("utf-8")]


@pytest.mark.asyncio
async def test_azure_blob_get_azure_blob_data_4(connector: AzureBlobConnector, storage, blob_content):
    """A gzip blob with empty lines is decompressed and the empty lines are ignored."""
    storage.write(
        "blob.json.gz", gzip.compress(blob_content + b"\n\n\n\n\n\n" + blob_content + b"\n" + blob_content + b"\n")
    )

    result = await connector.get_azure_blob_data()

    assert result == [blob_content.decode("utf-8") for _ in range(3)]


@pytest.mark.asyncio
async def test_azure_blob_growing_blob_is_not_forwarded_twice(connector: AzureBlobConnector, storage):
    """
    Azure appends lines to PT1H.json during the hour: each cycle forwards only the new lines
    and downloads only the new bytes (issue: duplicates and memory usage).
    """
    first_lines, new_lines = make_lines(3), make_lines(2, start=3)
    first_content = b"".join(line + b"\n" for line in first_lines)
    storage.write("PT1H.json", first_content)

    assert await connector.get_azure_blob_data() == [line.decode() for line in first_lines]

    storage.append("PT1H.json", b"".join(line + b"\n" for line in new_lines))
    storage.downloads.clear()

    assert await connector.get_azure_blob_data() == [line.decode() for line in new_lines]
    assert pushed_events(connector) == [line.decode() for line in first_lines + new_lines]
    # Only the appended bytes are downloaded
    assert [offset for _, offset, _ in storage.downloads] == [len(first_content)]

    # Nothing new: nothing forwarded, nothing downloaded
    storage.downloads.clear()
    assert await connector.get_azure_blob_data() == []
    assert storage.downloads == []


@pytest.mark.asyncio
async def test_azure_blob_last_line_being_written(connector: AzureBlobConnector, storage):
    """A last line cut in the middle is forwarded once complete, and only once."""
    storage.write("PT1H.json", b'{"id": 1}\n{"id": 2, "mess')

    assert await connector.get_azure_blob_data() == ['{"id": 1}']

    storage.append("PT1H.json", b'age": "end"}\n{"id": 3}')

    assert await connector.get_azure_blob_data() == ['{"id": 2, "message": "end"}', '{"id": 3}']

    storage.append("PT1H.json", b'\n{"id": 4}\n')

    assert await connector.get_azure_blob_data() == ['{"id": 4}']


@pytest.mark.asyncio
async def test_azure_blob_last_text_line_forwarded_once_blob_is_settled(connector: AzureBlobConnector, storage):
    """A last text line without newline is forwarded once the blob is no longer modified."""
    now = datetime.now(timezone.utc)
    storage.write("logs.txt", b"line 1\nline 2", modified_at=now)

    assert await connector.get_azure_blob_data() == ["line 1"]

    # Not modified since: the blob is listed again for its pending line, forwarded once settled
    storage.blobs["logs.txt"].last_modified = now - timedelta(minutes=10)
    with connector.context as cache:
        cache["last_event_date"] = now.isoformat()

    assert await connector.get_azure_blob_data() == ["line 2"]
    assert await connector.get_azure_blob_data() == []


@pytest.mark.asyncio
async def test_azure_blob_large_blob_read_by_chunks_and_pushed_by_batches(
    connector: AzureBlobConnector, storage, monkeypatch
):
    """The blob is downloaded by bounded ranges and forwarded by bounded batches (issue: OOMKilled)."""
    monkeypatch.setattr(azure_blob, "READ_CHUNK_SIZE", 100)
    connector.limit_of_events_to_push = 1000
    lines = make_lines(2500)
    storage.write("PT1H.json", b"".join(line + b"\n" for line in lines))

    result = await connector.get_azure_blob_data()

    assert result == [line.decode() for line in lines]
    assert all(length <= 100 for _, _, length in storage.downloads)
    assert [len(call.kwargs["events"]) for call in connector.push_data_to_intakes.call_args_list] == [1000, 1000, 500]


@pytest.mark.asyncio
async def test_azure_blob_large_gzip_blob_read_by_chunks_and_pushed_by_batches(
    connector: AzureBlobConnector, storage, monkeypatch
):
    """A gzip blob is downloaded, decompressed and forwarded by bounded chunks."""
    monkeypatch.setattr(azure_blob, "READ_CHUNK_SIZE", 100)
    connector.limit_of_events_to_push = 1000
    lines = make_lines(2500)
    storage.write("PT1H.json.gz", gzip_lines(*lines))

    result = await connector.get_azure_blob_data()

    assert result == [line.decode() for line in lines]
    assert all(length <= 100 for _, _, length in storage.downloads)
    assert [len(call.kwargs["events"]) for call in connector.push_data_to_intakes.call_args_list] == [1000, 1000, 500]

    # Already forwarded and unchanged: not downloaded again
    storage.downloads.clear()
    storage.blobs["PT1H.json.gz"].last_modified = datetime.now(timezone.utc)
    assert await connector.get_azure_blob_data() == []
    assert storage.downloads == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,encode",
    [
        ("PT1H.json", lambda lines: b"".join(l + b"\n" for l in lines)),
        ("PT1H.json.gz", lambda lines: gzip_lines(*lines)),
    ],
)
async def test_azure_blob_resume_after_failure_without_duplicates(
    connector: AzureBlobConnector, storage, name, encode
):
    """
    When the connector fails in the middle of a blob, the next cycle resumes after the last forwarded batch
    (issue: data loss when the checkpoint was only saved at the end of the cycle).
    """
    connector.limit_of_events_to_push = 10
    lines = make_lines(35)
    storage.write(name, encode(lines))

    calls = 0

    async def push_then_fail(events: list[str]) -> list[str]:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise ConnectionError("intake unavailable")

        return events

    connector.push_data_to_intakes = AsyncMock(side_effect=push_then_fail)

    with pytest.raises(ConnectionError):
        await connector.get_azure_blob_data()

    connector.push_data_to_intakes = AsyncMock(side_effect=lambda events: events)
    result = await connector.get_azure_blob_data()

    assert result == [line.decode() for line in lines[20:]]


@pytest.mark.asyncio
async def test_azure_blob_gzip_blob_with_appended_member(connector: AzureBlobConnector, storage):
    """A gzip blob growing with a new gzip member: only the new lines are forwarded."""
    storage.write("PT1H.json.gz", gzip_lines(b"a", b"b"))
    assert await connector.get_azure_blob_data() == ["a", "b"]

    storage.append("PT1H.json.gz", gzip_lines(b"c"))
    assert await connector.get_azure_blob_data() == ["c"]


@pytest.mark.asyncio
async def test_azure_blob_recreated_blob_is_read_from_start(connector: AzureBlobConnector, storage):
    """A blob deleted and created again with the same name is read from the start."""
    storage.write("PT1H.json", b"a\nb\n")
    assert await connector.get_azure_blob_data() == ["a", "b"]

    storage.write("PT1H.json", b"c\nd\ne\n", created_at=datetime.now(timezone.utc) + timedelta(seconds=1))
    assert await connector.get_azure_blob_data() == ["c", "d", "e"]


@pytest.mark.asyncio
async def test_azure_blob_old_blob_states_are_forgotten(connector: AzureBlobConnector, storage):
    """The reading state of blobs not modified for a long time is removed from the context."""
    old = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    with connector.context as cache:
        cache["blobs"] = {
            "old.json": {"created": old, "compressed": False, "offset": 10, "lines": 0, "last_modified": old}
        }

    storage.write("PT1H.json", b"a\n")
    await connector.get_azure_blob_data()

    assert set(connector.get_blob_states()) == {"PT1H.json"}


@pytest.mark.asyncio
async def test_azure_blob_get_most_recent_blob(
    connector: AzureBlobConnector, session_faker, symphony_storage, blob_content, pushed_events_ids
):
    """
    Test AzureBlobConnector get events.

    Args:
        connector: AzureBlobConnector
        session_faker: Faker
        symphony_storage: str
        blob_content: bytes
        pushed_events_ids: list[str]
    """
    current_date = datetime.now(timezone.utc).replace(microsecond=0)

    # Try to put last event date higher to be 1 day ahead of the log file date
    with connector.context as cache:
        cache["last_event_date"] = (current_date - timedelta(days=1)).isoformat()

    azure_blob_storage_wrapper = MagicMock()

    properties1 = BlobProperties()
    properties1.last_modified = current_date
    properties1.name = session_faker.word()

    properties2 = BlobProperties()
    properties2.last_modified = current_date + timedelta(minutes=5)
    properties2.name = session_faker.word()

    properties3 = BlobProperties()
    properties3.last_modified = current_date + timedelta(minutes=7)
    properties3.name = session_faker.word()

    expected_blobs = [properties1, properties2, properties3]

    mock_list_blobs = MagicMock()
    mock_list_blobs.__aiter__.return_value = expected_blobs

    azure_blob_storage_wrapper.list_blobs.return_value = mock_list_blobs

    connector._azure_blob_storage_wrapper = azure_blob_storage_wrapper

    blobs_list = [n async for n in connector.get_most_recent_blobs(lower_bound=current_date + timedelta(minutes=2))]

    assert blobs_list == [properties2, properties3]


@pytest.mark.asyncio
async def test_azure_blob_append_in_the_same_second_is_read(connector: AzureBlobConnector, storage):
    """
    `last_modified` has a one-second resolution: lines appended in the same second as the previous cycle
    don't move `last_modified` past the last event date, but the blob is read again because it grew.
    """
    modified_at = datetime.now(timezone.utc).replace(microsecond=0)
    storage.write("PT1H.json", b"a\nb\n", modified_at=modified_at)
    assert await connector.get_azure_blob_data() == ["a", "b"]

    storage.append("PT1H.json", b"c\n", modified_at=modified_at)
    assert await connector.get_azure_blob_data() == ["c"]
