"""Default Azure Blob Storage connector."""

import hashlib
import zlib
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Iterator

import orjson
from azure.storage.blob import BlobProperties

from azure_helpers.io import is_gzip_compressed
from connectors.blob import AbstractAzureBlobConnector

# Size of each ranged download
READ_CHUNK_SIZE = 4 * 1024 * 1024

# A last line without a trailing newline is forwarded once the blob is not modified for this long.
# A writer that pauses longer than this in the middle of a line gets this line forwarded as two events
SETTLED_DELAY = timedelta(minutes=5)

# A longer line is not an event: it is skipped, without being kept in memory
MAX_LINE_SIZE = 16 * 1024 * 1024

# Lines are decoded with `errors="replace"`: an invalid UTF-8 byte must not fail the cycle (and block the other blobs)

# Decompress gzip blobs in gzip format (header + trailer)
GZIP_WBITS = 16 + zlib.MAX_WBITS

# The reading state of a blob keeps a fingerprint of the bytes preceding its offset. They are checked before
# reading the blob further: when they changed, the blob was overwritten and is read again from the start
FINGERPRINT_SIZE = 64


def fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class BlobOverwritten(Exception):
    """The content of a blob, before its saved offset, is not the one that was read."""


class LineReader:
    """
    Split the chunks of a blob into lines.

    Each line comes as `(line, size, tail)`: `line` is `None` when the line is longer than MAX_LINE_SIZE,
    `size` is its size and `tail` its last FINGERPRINT_SIZE bytes (both without the newline).
    """

    def __init__(self) -> None:
        # Line being read: its content, or only its last bytes once it is longer than MAX_LINE_SIZE
        self.buffer = b""
        self.size = 0

    def _add(self, data: bytes) -> None:
        self.size += len(data)
        self.buffer += data
        if self.size > MAX_LINE_SIZE:
            self.buffer = self.buffer[-FINGERPRINT_SIZE:]

    def feed(self, data: bytes) -> Iterator[tuple[bytes | None, int, bytes]]:
        """
        Return the lines ended by `data`.
        """
        start = 0
        while (end := data.find(b"\n", start)) != -1:
            self._add(data[start:end])
            yield self.end()
            start = end + 1

        self._add(data[start:])

    def end(self) -> tuple[bytes | None, int, bytes]:
        """
        Return the line being read (its size is 0 when there is none), and start a new line.
        """
        line, size = self.buffer, self.size
        self.buffer, self.size = b"", 0

        return (line if size <= MAX_LINE_SIZE else None), size, line[-FINGERPRINT_SIZE:]


class AzureBlobConnector(AbstractAzureBlobConnector):
    """Azure Blob Storage connector."""

    name = "AzureBlobConnector"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Reading states of the blobs, read when listing the blobs
        self._blob_states: dict[str, dict[str, Any]] = {}

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
        pending: set[str] = set()

        async for blob in self.azure_blob_wrapper().list_blobs():
            state = states.get(blob.name)

            # A blob read partially (interrupted cycle, last line still being written) is listed again
            has_pending_content = (
                state is not None
                and state.get("created") == self._creation_time(blob)
                and (state.get("size") != blob.size if state.get("compressed") else state.get("offset", 0) < blob.size)
            )

            # Azure gives last_modified to the second: a blob modified again within the second of the checkpoint
            # is listed again (`>=`), its reading state makes that free
            if has_pending_content:
                pending.add(blob.name)

            if blob.last_modified >= lower_bound or has_pending_content:
                yield blob

        # An old blob still being read (after an outage) keeps its state
        self.forget_old_blob_states(keep=pending)

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

    async def _download_after(
        self, blob: BlobProperties, offset: int, expected: str | None, context: dict[str, Any]
    ) -> AsyncGenerator[bytes, None]:
        """
        Download the blob from `offset`, after checking that the bytes preceding `offset` are the ones already
        read (their fingerprint is `expected`). These bytes are downloaded with the first chunk.

        `context["window"]` is set to the bytes preceding `offset`.

        Raises:
            BlobOverwritten: the blob was overwritten since it was read
        """
        if blob.size < offset:
            raise BlobOverwritten()

        start = max(0, offset - FINGERPRINT_SIZE)
        first = True
        async for data in self._download(blob, start):
            if first:
                first = False
                context["window"], data = data[: offset - start], data[offset - start :]
                if expected and fingerprint(context["window"]) != expected:
                    raise BlobOverwritten()

            if data:
                yield data

    @staticmethod
    async def _gunzip(
        chunks: AsyncGenerator[bytes, None], state: dict[str, Any]
    ) -> AsyncGenerator[bytes | None, None]:
        """
        Decompress a gzip stream (possibly made of several gzip members), with bounded output chunks.

        `None` is yielded at the end of each gzip member, with `state["offset"]` set to the compressed offset
        following the member (`state["offset"]` is the compressed offset of the first chunk on input) and
        `state["tail"]` to the fingerprint of the compressed bytes preceding it (`state["window"]` holds the
        bytes preceding the first chunk).
        `state["eof"]` tells, at the end, whether the last gzip member is complete.
        """
        position = state["offset"]
        decompressor = zlib.decompressobj(wbits=GZIP_WBITS)
        new_member = True
        async for chunk in chunks:
            window, data = state.get("window", b""), chunk
            position += len(chunk)

            def move_offset(remaining: bytes) -> None:
                consumed = (window + chunk[: len(chunk) - len(remaining)])[-FINGERPRINT_SIZE:]
                state["offset"], state["tail"] = position - len(remaining), fingerprint(consumed)

            while data:
                if new_member:
                    # Zero padding before a member (some writers pad to a block size) is skipped, like `gzip` does
                    data = data.lstrip(b"\x00")
                    move_offset(data)
                    if not data:
                        break

                    if decompressor.eof:
                        decompressor = zlib.decompressobj(wbits=GZIP_WBITS)
                    new_member = False

                yield decompressor.decompress(data, READ_CHUNK_SIZE)
                if decompressor.eof:
                    data = decompressor.unused_data
                    move_offset(data)
                    yield None
                    new_member = True
                else:
                    data = decompressor.unconsumed_tail

            state["window"] = (window + chunk)[-FINGERPRINT_SIZE:]

        yield decompressor.flush()
        state["eof"] = new_member or decompressor.eof

    def _is_last_line_complete(self, line: bytes | None, blob: BlobProperties) -> bool:
        """
        Tell if the last line of a blob, without a trailing newline, is a complete event.

        It is when it is a JSON document, or when the blob is no longer modified.
        """
        try:
            if line is not None and isinstance(orjson.loads(line), (dict, list)):
                return True
        except orjson.JSONDecodeError:
            pass

        return self._is_settled(blob)

    @staticmethod
    def _is_settled(blob: BlobProperties) -> bool:
        """Tell if the blob is no longer modified: its content won't be completed."""
        return blob.last_modified < datetime.now(timezone.utc) - SETTLED_DELAY

    def _decode(self, line: bytes | None, size: int, blob: BlobProperties) -> list[str]:
        """
        Return the event of a line: none for an empty line or a line longer than MAX_LINE_SIZE.
        """
        if line is None:
            self.log(message=f"Blob {blob.name}: a line of {size} bytes is too long, it is skipped", level="warning")
            return []

        return [line.decode("utf-8", errors="replace")] if line else []

    async def read_blob(self, blob: BlobProperties) -> AsyncGenerator[tuple[list[str], dict[str, Any] | None], None]:
        """
        Read the new lines of a blob, by batches, with the reading state to save once the batch is forwarded.

        Args:
            blob: BlobProperties

        Returns:
            AsyncGenerator[tuple[list[str], dict[str, Any] | None], None]:
        """
        created = self._creation_time(blob)
        modified = blob.last_modified.isoformat()
        state = self._blob_states.get(blob.name)

        while True:
            # New blob, or blob created again or overwritten: read it from the start
            if state is None or state.get("created") != created:
                if blob.size == 0:
                    return

                first_bytes = await self.azure_blob_wrapper().download_blob_range(blob.name, 0, 2)
                state = {"created": created, "compressed": is_gzip_compressed(first_bytes), "offset": 0, "lines": 0}

            changed = state.get("last_modified") != modified
            state = {**state, "last_modified": modified}

            if state["compressed"]:
                reader = self._read_gzip_blob(blob, state, changed)
            else:
                reader = self._read_plain_blob(blob, state, changed)

            try:
                # The content already read is checked before the first batch is yielded
                async for events, new_state in reader:
                    yield events, new_state

                return
            except BlobOverwritten:
                self.log(message=f"Blob {blob.name} was overwritten: it is read again from its start", level="info")
                state = None

    async def _read_plain_blob(
        self, blob: BlobProperties, state: dict[str, Any], changed: bool
    ) -> AsyncGenerator[tuple[list[str], dict[str, Any]], None]:
        offset = state["offset"]

        # The whole blob was already forwarded
        if blob.size == offset and not changed:
            return

        batch: list[str] = []
        reader = LineReader()
        # Bytes preceding the offset
        context: dict[str, Any] = {"window": b""}
        async for data in self._download_after(blob, offset, state.get("tail"), context):
            for line, size, tail in reader.feed(data):
                offset += size + 1
                context["window"] = (context["window"] + tail + b"\n")[-FINGERPRINT_SIZE:]
                batch.extend(self._decode(line, size, blob))

                if len(batch) >= self.limit_of_events_to_push:
                    yield batch, {**state, "offset": offset, "tail": fingerprint(context["window"])}
                    batch = []

        # The last line has no trailing newline: it may still be written
        line, size, tail = reader.end()
        if size and self._is_last_line_complete(line, blob):
            offset += size
            context["window"] = (context["window"] + tail)[-FINGERPRINT_SIZE:]
            batch.extend(self._decode(line, size, blob))

        yield batch, {**state, "offset": offset, "tail": fingerprint(context["window"])}

    async def _read_gzip_blob(
        self, blob: BlobProperties, state: dict[str, Any], changed: bool
    ) -> AsyncGenerator[tuple[list[str], dict[str, Any]], None]:
        # The whole blob was already forwarded
        if state.get("size") == blob.size and not changed:
            return

        # Compressed offset of the gzip member being read (with the fingerprint of the bytes preceding it),
        # and the number of its lines already forwarded (with their checksum, checked when they are skipped)
        offset, tail, lines_to_skip = state["offset"], state.get("tail"), state["lines"]
        expected_checksum = state.get("checksum")

        index = 0
        checksum = 0

        def progress(lines: int, size: int | None) -> dict[str, Any]:
            return {
                **state,
                "offset": offset,
                "tail": tail,
                "lines": lines,
                "checksum": checksum if lines else None,
                "size": size,
            }

        batch: list[str] = []
        reader = LineReader()
        gunzip_state: dict[str, Any] = {"offset": offset, "tail": tail}
        try:
            async for data in self._gunzip(self._download_after(blob, offset, tail, gunzip_state), gunzip_state):
                # End of a gzip member: it always ends a line, and the next member is read from its own offset
                if data is None:
                    line, size, _ = reader.end()
                    if size:
                        index += 1
                        if index > lines_to_skip:
                            batch.extend(self._decode(line, size, blob))

                    # The member has less lines than the ones already forwarded: it is not the member that was read
                    if index < lines_to_skip and expected_checksum is not None:
                        raise BlobOverwritten()

                    offset, tail, lines_to_skip, index = gunzip_state["offset"], gunzip_state["tail"], 0, 0
                    checksum = 0
                    if len(batch) >= self.limit_of_events_to_push:
                        yield batch, progress(0, None)
                        batch = []
                    continue

                for line, size, line_tail in reader.feed(data):
                    index += 1
                    checksum = zlib.crc32(line_tail if line is None else line, zlib.crc32(b"\n", checksum))
                    if index <= lines_to_skip:
                        # The lines skipped are not the ones that were forwarded
                        if index == lines_to_skip and expected_checksum not in (None, checksum):
                            raise BlobOverwritten()
                        continue

                    batch.extend(self._decode(line, size, blob))

                    if len(batch) >= self.limit_of_events_to_push:
                        yield batch, progress(index, None)
                        batch = []

        except zlib.error as error:
            # Corrupted gzip data: the lines decoded so far are forwarded, the rest of the blob is skipped
            self.log(
                message=f"Blob {blob.name} is not a valid gzip stream after offset {offset} ({error}): "
                "its remaining content is skipped",
                level="error",
            )
            yield batch, progress(index, blob.size) if index >= lines_to_skip else {**state, "size": blob.size}
            return

        # The last gzip member is truncated (blob being written): its remaining lines are read next time
        if not gunzip_state["eof"] and not self._is_settled(blob):
            yield batch, progress(index, None) if index >= lines_to_skip else {**state, "size": None}
            return

        # The last gzip member is truncated and the blob is no longer modified (writer stopped): its partial last
        # line is forwarded and the blob is not read again until it is modified
        if not gunzip_state["eof"]:
            self.log(
                message=f"Blob {blob.name}: the gzip member at offset {offset} is truncated, "
                "its partial last line is forwarded",
                level="warning",
            )
            line, size, _ = reader.end()
            if size and index >= lines_to_skip:
                batch.extend(self._decode(line, size, blob))
            yield batch, progress(index, blob.size) if index >= lines_to_skip else {**state, "size": blob.size}
            return

        # Every member is complete: the next one starts after the last member and its padding
        offset, tail = gunzip_state["offset"], gunzip_state["tail"]
        yield batch, progress(0, blob.size)
