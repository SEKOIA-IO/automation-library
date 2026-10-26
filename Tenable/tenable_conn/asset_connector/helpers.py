from datetime import datetime
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
    timestamps: list[int] = []
    for field in ("last_found", "last_fixed"):
        value = vuln.get(field)
        if not value:
            continue
        try:
            timestamps.append(int(datetime.fromisoformat(value).timestamp()))
        except (ValueError, TypeError):
            continue
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
    Parse an ISO 8601 datetime string to a Unix timestamp.
    :param datetime_str: The ISO 8601 datetime string.
    :return: The Unix timestamp as an integer, or None if parsing fails.
    """
    if not datetime_str:
        return None
    try:
        dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except (ValueError, AttributeError, TypeError):
        return None


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
