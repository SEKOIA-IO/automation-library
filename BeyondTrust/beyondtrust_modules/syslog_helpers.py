import re
from collections.abc import Generator, Iterable
from dataclasses import dataclass

# Pattern: <date> <tenant_id> <appname>[<pid>]: <number>:<part_number>:<total_parts>:<payload>
SYSLOG_LINE_PATTERN = re.compile(
    r"^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"  # date (e.g. "Mar 10 11:55:00")
    r"(\S+)\s+"  # tenant_id
    r"(\S+)\[(\d+)\]:\s+"  # appname[pid]
    r"(\d+):(\d+):(\d+):"  # number:part_number:total_parts
    r"(.*)"  # payload
)

WHEN_PATTERN = re.compile(r"(?:^|;)when=(\d+)")


@dataclass
class SyslogRecord:
    date_str: str
    tenant_id: str
    appname: str
    pid: int
    number: int
    part_number: int
    total_parts: int
    payload: str


def parse_syslog_line(line: str) -> SyslogRecord | None:
    """Parse a single syslog line into a SyslogRecord, or None if it doesn't match."""
    match = SYSLOG_LINE_PATTERN.match(line)
    if not match:
        return None

    return SyslogRecord(
        date_str=match.group(1),
        tenant_id=match.group(2),
        appname=match.group(3),
        pid=int(match.group(4)),
        number=int(match.group(5)),
        part_number=int(match.group(6)),
        total_parts=int(match.group(7)),
        payload=match.group(8),
    )


def iter_reassembled_records(lines: Iterable[str]) -> Generator[str, None, None]:
    """Parse syslog lines and yield reassembled payloads as they become complete.

    Single-part records are yielded immediately. Multi-part records are buffered
    until all parts arrive, then concatenated and yielded. Memory usage is
    proportional to in-flight partial records, not the total input size.
    """
    buffer: dict[tuple[int, int], list[SyslogRecord]] = {}

    for line in lines:
        record = parse_syslog_line(line)
        if record is None:
            continue

        # Single-part record — yield immediately, no buffering
        if record.total_parts == 1:
            yield record.payload
            continue

        # Multi-part — buffer until all parts arrive
        key = (record.pid, record.number)
        if key not in buffer:
            buffer[key] = []
        buffer[key].append(record)

        if len(buffer[key]) == record.total_parts:
            parts = sorted(buffer.pop(key), key=lambda r: r.part_number)
            yield "".join(part.payload for part in parts)

    # Flush any remaining incomplete records
    for key in list(buffer):
        parts = sorted(buffer.pop(key), key=lambda r: r.part_number)
        payload = "".join(part.payload for part in parts)
        if payload:
            yield payload


def extract_when_timestamp(payload: str) -> int | None:
    """Extract the 'when' unix timestamp from a key=value syslog payload."""
    match = WHEN_PATTERN.search(payload)

    return int(match.group(1)) if match else None
