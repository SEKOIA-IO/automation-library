"""Default Azure Blob Storage connector."""

import zlib
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator

import orjson
from azure.storage.blob import BlobProperties

from azure_helpers.io import is_gzip_compressed
from connectors.blob import AbstractAzureBlobConnector

# Size of each ranged download
READ_CHUNK_SIZE = 4 * 1024 * 1024

# A last line without a trailing newline is forwarded once the blob is not modified for this long
SETTLED_DELAY = timedelta(minutes=5)

# Decompress gzip blobs in gzip format (header + trailer)
GZIP_WBITS = 16 + zlib.MAX_WBITS


class AzureBlobConnector(AbstractAzureBlobConnector):
    """Azure Blob Storage connector."""

    name = "AzureBlobConnector"

    # Reading states of the blobs, read when listing the blobs
    _blob_states: dict[str, dict[str, Any]] = {}

    def filter_blob_data(self, data: str) -> list[str]:
        """
        Filter blob data and exclude empty lines.

        Args:
            data: str

        Returns:
            list[dict[str, Any]]:
        """
        return [line for line in data.split("\n") if line != ""]

    async def get_most_recent_blobs(self, lower_bound: datetime) -> AsyncGenerator[BlobProperties, None]:
        """
        Return the blobs modified after lower_bound, and the blobs whose last line is not forwarded yet.

        Args:
            lower_bound: datetime

        Returns:
            AsyncGenerator[BlobProperties, None]
        """
        # Read the states once per cycle (each blob is listed once per cycle)
        self._blob_states = states = self.get_blob_states()

        async for blob in self.azure_blob_wrapper().list_blobs():
            state = states.get(blob.name)
            has_pending_line = (
                state is not None
                and not state.get("compressed")
                and state.get("created") == self._creation_time(blob)
                and state.get("offset", 0) < blob.size
            )

            if blob.last_modified > lower_bound or has_pending_line:
                yield blob

    @staticmethod
    def _creation_time(blob: BlobProperties) -> str | None:
        return blob.creation_time.isoformat() if blob.creation_time else None

    async def _download(self, blob: BlobProperties, offset: int) -> AsyncGenerator[bytes, None]:
        """
        Download the blob from `offset` to its listed size, by chunks of READ_CHUNK_SIZE bytes.
        """
        while offset < blob.size:
            length = min(READ_CHUNK_SIZE, blob.size - offset)
            data = await self.azure_blob_wrapper().download_blob_range(blob.name, offset, length)
            if not data:
                break

            offset += len(data)
            yield data

    @staticmethod
    async def _gunzip(chunks: AsyncGenerator[bytes, None], state: dict[str, Any]) -> AsyncGenerator[bytes, None]:
        """
        Decompress a gzip stream (possibly made of several gzip members), with bounded output chunks.

        `state["eof"]` tells, at the end, whether the last gzip member is complete.
        """
        decompressor = zlib.decompressobj(wbits=GZIP_WBITS)
        async for data in chunks:
            while data:
                if decompressor.eof:
                    decompressor = zlib.decompressobj(wbits=GZIP_WBITS)

                yield decompressor.decompress(data, READ_CHUNK_SIZE)
                data = decompressor.unused_data if decompressor.eof else decompressor.unconsumed_tail

        yield decompressor.flush()
        state["eof"] = decompressor.eof

    def _is_last_line_complete(self, line: bytes, blob: BlobProperties) -> bool:
        """
        Tell if the last line of a blob, without a trailing newline, is a complete event.

        It is when it is a JSON document, or when the blob is no longer modified.
        """
        try:
            if isinstance(orjson.loads(line), (dict, list)):
                return True
        except orjson.JSONDecodeError:
            pass

        return blob.last_modified < datetime.now(timezone.utc) - SETTLED_DELAY

    async def read_blob(self, blob: BlobProperties) -> AsyncGenerator[tuple[list[str], dict[str, Any] | None], None]:
        """
        Read the new lines of a blob, by batches, with the reading state to save once the batch is forwarded.

        Args:
            blob: BlobProperties

        Returns:
            AsyncGenerator[tuple[list[str], dict[str, Any] | None], None]:
        """
        created = self._creation_time(blob)
        state = self._blob_states.get(blob.name)

        # New blob, or blob deleted and created again: read it from the start
        if state is None or state.get("created") != created:
            if blob.size == 0:
                return

            first_bytes = await self.azure_blob_wrapper().download_blob_range(blob.name, 0, 2)
            state = {"created": created, "compressed": is_gzip_compressed(first_bytes), "offset": 0, "lines": 0}

        state["last_modified"] = blob.last_modified.isoformat()

        if state["compressed"]:
            reader = self._read_gzip_blob(blob, state)
        else:
            reader = self._read_plain_blob(blob, state)

        async for events, new_state in reader:
            yield events, new_state

    async def _read_plain_blob(
        self, blob: BlobProperties, state: dict[str, Any]
    ) -> AsyncGenerator[tuple[list[str], dict[str, Any]], None]:
        offset = state["offset"]

        # The blob was overwritten with a smaller content: read it again from the start
        if blob.size < offset:
            offset = 0

        batch: list[str] = []
        buffer = b""
        async for data in self._download(blob, offset):
            *lines, buffer = (buffer + data).split(b"\n")
            for line in lines:
                offset += len(line) + 1
                if line:
                    batch.append(line.decode("utf-8"))

                if len(batch) >= self.limit_of_events_to_push:
                    yield batch, {**state, "offset": offset}
                    batch = []

        # The last line has no trailing newline: it may still be written
        if buffer and self._is_last_line_complete(buffer, blob):
            offset += len(buffer)
            batch.append(buffer.decode("utf-8"))

        yield batch, {**state, "offset": offset}

    async def _read_gzip_blob(
        self, blob: BlobProperties, state: dict[str, Any]
    ) -> AsyncGenerator[tuple[list[str], dict[str, Any]], None]:
        # The whole blob was already forwarded
        if state.get("size") == blob.size:
            return

        lines_to_skip = state["lines"]
        index = 0

        batch: list[str] = []
        buffer = b""
        gunzip_state: dict[str, Any] = {}
        async for data in self._gunzip(self._download(blob, 0), gunzip_state):
            *lines, buffer = (buffer + data).split(b"\n")
            for line in lines:
                index += 1
                if index <= lines_to_skip:
                    continue

                if line:
                    batch.append(line.decode("utf-8"))

                if len(batch) >= self.limit_of_events_to_push:
                    yield batch, {**state, "lines": index, "size": None}
                    batch = []

        # The gzip stream is truncated (blob being written): wait for the rest
        if not gunzip_state["eof"]:
            yield batch, {**state, "lines": max(index, lines_to_skip), "size": None}
            return

        if buffer:
            index += 1
            if index > lines_to_skip:
                batch.append(buffer.decode("utf-8"))

        yield batch, {**state, "lines": max(index, lines_to_skip), "size": blob.size}
