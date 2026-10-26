from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Iterable, NamedTuple

from tenable_conn.asset_connector.models.asset_details_model import AssetDetails
from tenable_conn.asset_connector.models.assets_export_model import (
    AssetCloud,
    AssetExportV2,
    AssetNetwork,
    AssetTimestamps,
    AwsCloud,
    AzureCloud,
    GcpCloud,
    NetworkInterfaceV2 as TenableNetworkInterface,
)

# Platform limits of the asset management API
DESCRIPTION_MAX_LENGTH = 1024
REFERENCE_MAX_LENGTH = 512
REFERENCES_MAX_COUNT = 20
TRUNCATION_SUFFIX = " [...] see more on the Tenable product"


class FindingKey(NamedTuple):
    finding_id: str
    state: str | None
    last_found: str | None
    last_fixed: str | None


def effective_timestamp(vuln: dict) -> int | None:
    """
    Compute the timestamp a finding is filtered on by Tenable's `since`: the latest of `last_found` and
    `last_fixed`, so FIXED findings also move the checkpoint.
    :param vuln: The raw vulnerability dictionary.
    :return: The timestamp in epoch seconds, or None when neither date is present and valid.
    """
    timestamps = [
        timestamp
        for timestamp in (parse_datetime_to_timestamp(vuln.get(field)) for field in ("last_found", "last_fixed"))
        if timestamp is not None
    ]
    return max(timestamps) if timestamps else None


def dedup_key(vuln: dict) -> FindingKey | None:
    """
    Build the key identifying one version of a finding.
    :param vuln: The raw vulnerability dictionary.
    :return: The dedup key, or None when the finding has no `finding_id`.
    """
    finding_id = vuln.get("finding_id")
    if not finding_id:
        return None
    return FindingKey(
        finding_id=finding_id,
        state=vuln.get("state"),
        last_found=vuln.get("last_found"),
        last_fixed=vuln.get("last_fixed"),
    )


def boundary_to_json(boundary: Iterable[FindingKey]) -> list[dict]:
    """
    Serialize the boundary for `context.json`: one dict per key, in a stable order.
    :param boundary: The boundary keys.
    :return: A list of dicts with the `FindingKey` fields.
    """
    return [key._asdict() for key in sorted(boundary, key=str)]


def boundary_from_json(items: list | None) -> set[FindingKey]:
    """
    Read the boundary stored in `context.json`. Entries that are not a valid key are ignored: at worst the
    corresponding finding is sent once more.
    :param items: The stored list of dicts (None when the key is missing).
    :return: The boundary keys.
    """
    boundary: set[FindingKey] = set()
    for item in items or []:
        if isinstance(item, dict) and item.get("finding_id"):
            boundary.add(
                FindingKey(
                    finding_id=item["finding_id"],
                    state=item.get("state"),
                    last_found=item.get("last_found"),
                    last_fixed=item.get("last_fixed"),
                )
            )
    return boundary


def advance_checkpoint(
    cursor: int | None, boundary: set[FindingKey], finding_time: int | None, finding_key: FindingKey | None
) -> int | None:
    """
    Include one processed finding in the checkpoint being built during a traversal.

    :param cursor: The latest finding time seen so far (None during an initial sync before any finding).
    :param boundary: The keys of the findings at `cursor`, updated in place.
    :param finding_time: The effective timestamp of the finding (None: the finding is ignored).
    :param finding_key: The dedup key of the finding, None to keep it out of the boundary (failed finding).
    :return: The new cursor.
    """
    if finding_time is None:
        return cursor
    if cursor is None or finding_time > cursor:
        boundary.clear()
        cursor = finding_time
    if finding_time == cursor and finding_key:
        boundary.add(finding_key)
    return cursor


def parse_datetime_to_timestamp(datetime_str: str | None) -> int | None:
    """
    Parse an ISO 8601 datetime string to a Unix timestamp. A datetime without timezone is read as UTC, so the
    result does not depend on the local timezone of the container.
    :param datetime_str: The ISO 8601 datetime string.
    :return: The Unix timestamp as an integer, or None if parsing fails.
    """
    if not datetime_str:
        return None
    try:
        dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp())


def truncate_description(description: str | None) -> str:
    """
    Return only the first sentence of a description, appending a reference to Tenable.
    :param description: The full description string.
    :return: The first sentence followed by 'See more details on Tenable'.
    """
    if not description:
        return "See more details on Tenable"
    sentence_end = -1
    for i, ch in enumerate(description):
        if ch in (".", "!", "?"):
            sentence_end = i
            break
    first_sentence = description[: sentence_end + 1].strip() if sentence_end != -1 else description.strip()
    return f"{first_sentence} See more details on Tenable"


def limit_description(description: str) -> str:
    """
    Cap a description to the platform limit, with a suffix pointing to Tenable when it is cut.
    :param description: The description.
    :return: The description, at most DESCRIPTION_MAX_LENGTH characters long.
    """
    if len(description) <= DESCRIPTION_MAX_LENGTH:
        return description
    return description[: DESCRIPTION_MAX_LENGTH - len(TRUNCATION_SUFFIX)] + TRUNCATION_SUFFIX


def limit_references(references: list[str] | None) -> list[str]:
    """
    Cap the references to the platform limits: at most REFERENCES_MAX_COUNT items; a reference longer than
    REFERENCE_MAX_LENGTH is dropped rather than cut, since a truncated URL is useless.
    :param references: The reference URLs.
    :return: The capped list.
    """
    kept = [reference for reference in (references or []) if len(reference) <= REFERENCE_MAX_LENGTH]
    return kept[:REFERENCES_MAX_COUNT]


def asset_details_to_export(details: AssetDetails) -> AssetExportV2:
    """
    Convert a Get Asset Details payload into the AssetExportV2 shape.

    The Export Assets v2 chunk and the Get Asset Details endpoint expose the same
    information under different field names. This adapter lets the fallback API call
    feed the same downstream logic (device building) as the export-based cache.
    :param details: The AssetDetails model parsed from the Get Asset Details endpoint.
    :return: An AssetExportV2 model populated from the details payload.
    """
    network_interfaces = [
        TenableNetworkInterface(
            name=iface.name,
            mac_addresses=iface.mac_address,
            ipv4s=iface.ipv4,
            ipv6s=iface.ipv6,
            fqdns=iface.fqdn,
            virtual=iface.virtual,
            aliased=iface.aliased,
        )
        for iface in (details.interfaces or [])
    ]

    # The "name" label is carried by `name`, not injected into the hostnames, so the device hostname follows
    # the same fallback order for exported and fallback-fetched assets
    hostnames = details.hostname or []

    network = AssetNetwork(
        ipv4s=details.ipv4 or [],
        ipv6s=details.ipv6 or [],
        fqdns=details.fqdn or [],
        mac_addresses=details.mac_address or [],
        netbios_names=details.netbios_name or [],
        hostnames=hostnames,
        network_interfaces=network_interfaces,
    )

    timestamps = AssetTimestamps(
        created_at=details.created_at,
        updated_at=details.updated_at,
        deleted_at=details.deleted_at,
        terminated_at=details.terminated_at,
        first_seen=details.first_seen,
        last_seen=details.last_seen,
    )

    azure_location = getattr(details, "azure_location", None)
    cloud = AssetCloud(
        aws=AwsCloud(region=details.aws_region[0]) if details.aws_region else None,
        azure=AzureCloud(location=azure_location[0]) if azure_location else None,
        gcp=GcpCloud(zone=details.gcp_zone[0]) if details.gcp_zone else None,
    )

    return AssetExportV2(
        id=details.id,
        name=details.name,
        has_agent=details.has_agent,
        operating_systems=details.operating_system or [],
        system_types=details.system_type or [],
        agent_names=details.agent_name or [],
        network=network,
        timestamps=timestamps,
        cloud=cloud,
    )


@dataclass
class TraversalState:
    """
    Checkpoint bookkeeping of one traversal of the vulnerability export (pure: no I/O, no logging).

    The committed checkpoint (cursor + boundary) is frozen for the traversal; the next checkpoint is the latest
    finding time seen with the keys of the findings at that time, capped so that findings whose asset lookup
    failed temporarily are fetched again.
    """

    committed_cursor: int | None
    committed_boundary: frozenset[FindingKey]
    # Captured before the export request: the cursor of an initial sync that returns no finding
    export_start: int
    next_cursor: int | None = field(init=False)
    next_boundary: set[FindingKey] = field(init=False)
    # Earliest time of a finding whose asset lookup failed temporarily: the committed cursor must not pass it,
    # otherwise Tenable's `since` filter never returns that finding again
    retry_from: int | None = None
    retry_count: int = 0
    generated: int = 0
    deduplicated: int = 0
    skipped: int = 0

    def __post_init__(self) -> None:
        self.next_cursor = self.committed_cursor
        self.next_boundary = set(self.committed_boundary)

    @property
    def initial_sync(self) -> bool:
        """No committed cursor: the export has no `since` filter."""
        return self.committed_cursor is None

    def cap_time(self, raw_time: int | None) -> int | None:
        """
        An export is a snapshot: a finding dated after the export start is tracked at the export start, otherwise
        `since` would move into the future and skip every finding until then.
        :param raw_time: The effective timestamp of the finding.
        :return: The time used for the checkpoint.
        """
        if raw_time is not None and raw_time > self.export_start:
            return self.export_start
        return raw_time

    def already_sent(self, raw_time: int | None, finding_time: int | None, finding_key: FindingKey | None) -> bool:
        """
        Whether a previous run already sent this version of the finding: it is in the committed boundary and
        either at the committed second (Tenable's inclusive `since` filter) or dated in the future (tracked at
        the export start, so returned by every export until its date).
        :param raw_time: The effective timestamp of the finding.
        :param finding_time: The capped timestamp of the finding.
        :param finding_key: The dedup key of the finding.
        """
        return (
            finding_time is not None
            and finding_key is not None
            and finding_key in self.committed_boundary
            and (finding_time == self.committed_cursor or (raw_time is not None and raw_time > self.export_start))
        )

    def track(self, finding_time: int | None, finding_key: FindingKey | None) -> None:
        """
        Include one processed finding in the next checkpoint.
        :param finding_time: The capped timestamp of the finding (None: ignored).
        :param finding_key: Its dedup key, None to keep it out of the boundary (failed finding, retried).
        """
        self.next_cursor = advance_checkpoint(self.next_cursor, self.next_boundary, finding_time, finding_key)

    def record_lookup_failure(self, finding_time: int | None) -> None:
        """
        Record a finding whose asset lookup failed temporarily; a finding without timestamp is retried from the
        committed cursor.
        :param finding_time: The capped timestamp of the finding.
        """
        self.retry_count += 1
        retry_time = finding_time if finding_time is not None else self.committed_cursor
        if retry_time is not None and (self.retry_from is None or retry_time < self.retry_from):
            self.retry_from = retry_time

    def next_checkpoint(self) -> tuple[int, set[FindingKey]]:
        """
        The checkpoint to commit after a complete traversal.

        An initial sync without any finding starts the incremental runs from the export start. When an asset
        lookup failed, the cursor is capped at the failed finding (the findings sent at that second are sent once
        more: duplicates, never a loss), or the committed checkpoint is kept when the failure is not after it.
        :return: The next cursor and boundary.
        """
        if self.next_cursor is None:
            return self.export_start, set()
        if self.retry_from is not None and self.retry_from < self.next_cursor:
            if self.committed_cursor is not None and self.retry_from <= self.committed_cursor:
                return self.committed_cursor, set(self.committed_boundary)
            return self.retry_from, set()
        return self.next_cursor, self.next_boundary
