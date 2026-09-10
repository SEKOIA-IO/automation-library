"""Shared THOR Cloud API client helpers used by both the connector and actions.

Targets the THOR Cloud / THOR Cloud Lite API (Swagger 2.0, basePath /api/v1).
Auth: raw API key in the `Authorization` header (type apiKey, no "Bearer" prefix).
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

ENDPOINTS = {
    "thor_cloud_lite": "https://thorcloud-lite.nextron-systems.com",
    "thor_cloud": "https://thorcloud.nextron-services.com",
}

SCAN_SEARCH_PATH = "/api/v1/scan/search"
SCAN_LOG_PATH = "/api/v1/scan/log"


def get_base_url(product: str) -> str:
    """Resolve the API base URL from the product selection."""
    return ENDPOINTS.get(product, ENDPOINTS["thor_cloud_lite"])


def get_headers(api_key: str) -> dict:
    """Build authenticated request headers.

    The THOR Cloud API expects the raw API key in the Authorization header
    (Swagger securityDefinition ApiKeyAuth: type apiKey, in header) — no "Bearer" prefix.
    """
    return {
        "Authorization": api_key,
        "Accept": "application/json",
    }


def parse_campaigns(campaigns: Optional[str]) -> Optional[list[str]]:
    """Split a comma-separated campaign UUID string into a clean list.

    The Sekoia UI exposes the `campaigns` config as a single textbox, so multiple
    UUIDs are entered comma-separated. Returns None when empty (query all campaigns).
    """
    if not campaigns:
        return None
    ids = [c.strip() for c in campaigns.split(",") if c.strip()]
    return ids or None


def _to_epoch_seconds(value: Optional[int]) -> Optional[float]:
    """Normalize an epoch timestamp that may be in seconds or milliseconds."""
    if value is None:
        return None
    return value / 1000 if value > 1_000_000_000_000 else float(value)


def scan_creation_epoch(scan: dict) -> Optional[float]:
    """Return a scan's creation time as epoch seconds, if available."""
    return _to_epoch_seconds(scan.get("creation_date"))


def fetch_scans(
    base_url: str,
    headers: dict,
    days_back: int,
    campaigns: Optional[list[str]] = None,
    limit: int = 100,
) -> list[dict]:
    """Fetch scans created within the lookback window, newest first.

    The search response is a datatable wrapper: {"data": [...], "total": N}.
    Scans expose `id` (UUID), `creation_date` (epoch int), `campaign_id`, `available_logs`, etc.
    The API filters by a single `campaign`; multiple campaigns are queried in turn.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp()
    scans: list[dict] = []

    campaign_filters: list[Optional[str]] = list(campaigns) if campaigns else [None]
    for campaign in campaign_filters:
        offset = 0
        while True:
            params: dict[str, str | int] = {
                "limit": limit,
                "offset": offset,
                "order_field": "creation_date",
                "order_dir": "DESC",  # API enum is uppercase ASC/DESC
            }
            if campaign:
                params["campaign"] = campaign

            response = requests.get(urljoin(base_url, SCAN_SEARCH_PATH), headers=headers, params=params, timeout=30)
            response.raise_for_status()

            batch = response.json().get("data") or []
            if not batch:
                break

            stop = False
            for scan in batch:
                created = _to_epoch_seconds(scan.get("creation_date"))
                if created is None or created >= cutoff:
                    scans.append(scan)
                else:
                    stop = True  # ordered desc: everything after is older
                    break

            if stop or len(batch) < limit:
                break
            offset += limit

    return scans


def fetch_scan_logs(base_url: str, headers: dict, scan_id: str, log_type: str = "thor.json") -> list[dict]:
    """Download and parse a scan's NDJSON log (log=thor.json) via /api/v1/scan/log.

    Streams the response line-by-line so very large scans don't have to be
    materialized in memory, and skips malformed NDJSON lines so a single bad
    entry does not discard the whole scan.
    """
    events: list[dict] = []
    with requests.get(
        urljoin(base_url, SCAN_LOG_PATH),
        headers=headers,
        params={"scan": scan_id, "log": log_type},
        timeout=60,
        stream=True,
    ) as response:
        response.raise_for_status()
        response.encoding = "utf-8"  # NDJSON is UTF-8; avoid requests' ISO-8859-1 fallback for text/*
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("Skipping malformed NDJSON line in scan %s", scan_id)

    return events
