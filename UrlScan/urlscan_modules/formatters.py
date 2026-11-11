"""Pure functions that turn urlscan.io responses into the summaries the actions return."""

import ipaddress
import re
from typing import Any

# Summary key -> key in the urlscan.io response, one table per summary section.
PAGE_FIELDS = {
    "url": "url",
    "domain": "domain",
    "apex_domain": "apexDomain",
    "ip": "ip",
    "ptr": "ptr",
    "asn": "asn",
    "asn_name": "asnname",
    "country": "country",
    "city": "city",
    "server": "server",
    "title": "title",
    "status": "status",
    "mime_type": "mimeType",
    "redirected": "redirected",
    "domain_age_days": "domainAgeDays",
    "tls_issuer": "tlsIssuer",
    "tls_valid_days": "tlsValidDays",
}
CONTACTED_FIELDS = ("domains", "ips", "countries", "asns")
VERDICT_LIST_FIELDS = ("categories", "brands", "tags")
STATS_FIELDS = {"malicious": "malicious", "secure_percentage": "securePercentage"}
DOWNLOADED_FILE_FIELDS = {
    "filename": "filename",
    "sha256": "sha256",
    "size": "filesize",
    "mime_type": "mimeType",
    "mime_description": "mimeDescription",
    "url": "url",
    "state": "state",
}
# Search row key -> path in a search hit.
SEARCH_ROW_FIELDS = {
    "scan_time": ("task", "time"),
    "submitted_url": ("task", "url"),
    "visibility": ("task", "visibility"),
    "page_url": ("page", "url"),
    "page_domain": ("page", "domain"),
    "page_ip": ("page", "ip"),
    "page_asn": ("page", "asn"),
    "page_asn_name": ("page", "asnname"),
    "page_country": ("page", "country"),
    "page_title": ("page", "title"),
    "page_status": ("page", "status"),
    "malicious": ("verdicts", "malicious"),
    "score": ("verdicts", "score"),
    "result_api_url": ("result",),
    "screenshot_url": ("screenshot",),
}


def _section(source: Any, key: str) -> dict[str, Any]:
    """A response section; any section may be missing or null, for example when the page did not load."""
    value = source.get(key) if isinstance(source, dict) else None
    return value if isinstance(value, dict) else {}


def _items(source: dict[str, Any], key: str) -> list[Any]:
    value = source.get(key)
    return list(value) if isinstance(value, list) else []


def empty_scan_summary() -> dict[str, Any]:
    """The full shape of a scan summary: scalars are None, lists are empty."""
    return {
        "uuid": None,
        "status": None,
        "submitted_url": None,
        "visibility": None,
        "scan_time": None,
        "tags": [],
        "verdict": {
            "malicious": None,
            "score": None,
            "categories": [],
            "brands": [],
            "tags": [],
            "engines_malicious": None,
            "engines_total": None,
            "community_votes_malicious": None,
        },
        "page": dict.fromkeys(PAGE_FIELDS),
        "brand": None,
        "contacted": {name: [] for name in CONTACTED_FIELDS},
        "stats": {"requests": None, "malicious": None, "secure_percentage": None},
        "downloaded_files": [],
        "report_url": None,
        "result_api_url": None,
        "screenshot_available": None,
        "screenshot_url": None,
        "dom_available": None,
        "dom_url": None,
        "comment": None,
    }


def downloaded_files(items: Any) -> list[dict[str, Any]]:
    """Files downloaded by the scanned page, from `meta.processors.download.data`."""
    if not isinstance(items, list):
        return []
    return [
        {name: item.get(source) for name, source in DOWNLOADED_FILE_FIELDS.items()}
        for item in items
        if isinstance(item, dict)
    ]


def build_scan_summary(
    result: dict[str, Any], base_url: str, submission: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Summary of a finished scan; `submission` only supplies the raw result API URL."""
    task = _section(result, "task")
    verdicts = _section(result, "verdicts")
    overall = _section(verdicts, "overall")
    page = _section(result, "page")
    lists = _section(result, "lists")
    stats = _section(result, "stats")
    requests = _section(result, "data").get("requests")
    processors = _section(_section(result, "meta"), "processors")
    uuid = task.get("uuid")

    summary = empty_scan_summary()
    summary.update(
        uuid=uuid,
        status="done",
        submitted_url=task.get("url"),
        visibility=task.get("visibility"),
        scan_time=task.get("time"),
        tags=_items(task, "tags"),
        brand=_section(result, "visible").get("brandname"),
        downloaded_files=downloaded_files(_section(processors, "download").get("data")),
        report_url=task.get("reportURL"),
        result_api_url=(submission or {}).get("api") or f"{base_url}/api/v1/result/{uuid}/",
        screenshot_url=task.get("screenshotURL"),
        dom_url=task.get("domURL"),
    )
    summary["verdict"].update(
        malicious=overall.get("malicious"),
        score=overall.get("score"),
        engines_malicious=_section(verdicts, "engines").get("maliciousTotal"),
        engines_total=_section(verdicts, "engines").get("enginesTotal"),
        community_votes_malicious=_section(verdicts, "community").get("votesMalicious"),
    )
    for name in VERDICT_LIST_FIELDS:
        summary["verdict"][name] = _items(overall, name)
    summary["page"] = {name: page.get(source) for name, source in PAGE_FIELDS.items()}
    summary["contacted"] = {name: _items(lists, name) for name in CONTACTED_FIELDS}
    summary["stats"] = {"requests": len(requests) if isinstance(requests, list) else None} | {
        name: stats.get(source) for name, source in STATS_FIELDS.items()
    }
    return summary


def submitted_summary(submission: dict[str, Any], base_url: str) -> dict[str, Any]:
    """Summary returned right after the submission, before the scan is finished."""
    uuid = submission.get("uuid")
    return empty_scan_summary() | {
        "uuid": uuid,
        "status": "submitted",
        "submitted_url": submission.get("url"),
        "visibility": submission.get("visibility"),
        "report_url": submission.get("result"),
        "result_api_url": submission.get("api") or f"{base_url}/api/v1/result/{uuid}/",
    }


def blacklisted_summary(url: str) -> dict[str, Any]:
    """Summary returned when urlscan.io refuses to scan a blacklisted URL."""
    return empty_scan_summary() | {"status": "blacklisted", "submitted_url": url}


def build_indicator_query(indicator: str) -> str:
    """Search query for an IP, SHA256, URL or domain."""
    value = indicator.strip()
    quoted = '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    try:
        ipaddress.ip_address(value)
        return f"ip:{quoted}"
    except ValueError:
        pass
    if re.fullmatch(r"[0-9a-fA-F]{64}", value):
        return f"hash:{quoted}"
    if value.startswith(("http://", "https://")):
        return f"page.url:{quoted}"
    return f"domain:{quoted}"


def _search_row(hit: dict[str, Any], base_url: str) -> dict[str, Any]:
    uuid = hit.get("_id")
    row: dict[str, Any] = {"uuid": uuid}
    for name, path in SEARCH_ROW_FIELDS.items():
        source: Any = hit
        for key in path[:-1]:
            source = _section(source, key)
        row[name] = source.get(path[-1]) if isinstance(source, dict) else None
    row["report_url"] = f"{base_url}/result/{uuid}/" if uuid else None
    row["files"] = downloaded_files(hit.get("files"))
    return row


def build_search_results(response: dict[str, Any], query: str, size: int, base_url: str) -> dict[str, Any]:
    """One page of search results; `next_search_after` is None on the last page."""
    hits = [hit for hit in _items(response, "results") if isinstance(hit, dict)]
    sort = hits[-1].get("sort") if hits else None
    next_search_after = None
    if len(hits) >= size and isinstance(sort, list) and sort:
        next_search_after = ",".join(str(value) for value in sort)
    return {
        "query": query,
        "total": response.get("total"),
        "has_more": response.get("has_more"),
        "took": response.get("took"),
        "search_date_limit_days": response.get("search_date_limit_days"),
        "next_search_after": next_search_after,
        "results": [_search_row(hit, base_url) for hit in hits],
    }
