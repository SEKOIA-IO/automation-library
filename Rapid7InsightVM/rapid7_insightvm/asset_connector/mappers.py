"""Pure helpers mapping Rapid7 InsightVM records to OCSF objects.

They hold no state and do no I/O, so they can be shared by future connectors (device,
software) and tested without a connector instance.
"""

import html
import re
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import quote

from dateutil.parser import isoparse
from sekoia_automation.asset_connector.models.ocsf.base import Product
from sekoia_automation.asset_connector.models.ocsf.device import (
    Device,
    DeviceTypeId,
    DeviceTypeStr,
    OperatingSystem,
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.asset_connector.models.ocsf.risk_level import RiskLevelId, RiskLevelStr
from sekoia_automation.asset_connector.models.ocsf.vulnerability import CVE, CVSS, VulnerabilityDetails

from rapid7_insightvm.asset_connector.models import (
    Rapid7Asset,
    Rapid7Finding,
    Rapid7FindingResult,
    Rapid7Vulnerability,
    VulnerabilitySummary,
)

PRODUCT_NAME = "InsightVM"
VENDOR_NAME = "Rapid7"

MAX_DESC_LENGTH = 1024
MAX_REFERENCE_LENGTH = 512
MAX_REFERENCES = 20
TRUNCATION_SUFFIX = " [...] see more on the Rapid7 InsightVM product"

NVD_URL = "https://nvd.nist.gov/vuln/detail/{cve}"
VULNERABILITY_PAGE = "/vulnerability/vuln-summary.jsp?vulnid={vuln_id}"

# History events after which the findings of an asset may have changed.
ASSESSMENT_EVENT_TYPES = frozenset(
    {
        "SCAN",
        "AGENT-IMPORT",
        "SCAN-LOG-IMPORT",
        "ASSET-IMPORT",
        "EXTERNAL-IMPORT",
        "VULNERABILITY_EXCEPTION_APPLIED",
        "VULNERABILITY_EXCEPTION_UNAPPLIED",
    }
)

Severity = Literal["Unknown", "Medium", "High", "Critical"]

# InsightVM severity -> (OCSF severity, OCSF severity_id)
SEVERITY_MAP: dict[str, tuple[Severity, int]] = {
    "moderate": ("Medium", 3),
    "severe": ("High", 4),
    "critical": ("Critical", 5),
}
UNKNOWN_SEVERITY: tuple[Severity, int] = ("Unknown", 0)

# InsightVM severity -> OCSF risk level member name
RISK_LEVEL_MAP: dict[str, str] = {
    "moderate": "MEDIUM",
    "severe": "HIGH",
    "critical": "CRITICAL",
}

# Result status (without the "-with-exception-applied" suffix) -> (confidence, confidence_id)
CONFIDENCE_MAP: dict[str, tuple[str, int]] = {
    "vulnerable": ("High", 3),
    "vulnerable-version": ("Medium", 2),
    "vulnerable-potential": ("Low", 1),
}
EXCEPTION_SUFFIX = "-with-exception-applied"

# Keywords of the OS family / system name, first match wins -> OSTypeStr member name
OS_KEYWORDS: list[tuple[str, str]] = [
    ("windows", "WINDOWS"),
    ("android", "ANDROID"),
    ("mac os", "MACOS"),
    ("macos", "MACOS"),
    ("ios", "IOS"),
    ("solaris", "SOLARIS"),
    ("aix", "AIX"),
    ("hp-ux", "HPUX"),
    ("linux", "LINUX"),
]

# osFingerprint.type -> DeviceTypeStr member name
FINGERPRINT_TYPE_MAP: dict[str, str] = {
    "server": "SERVER",
    "workstation": "DESKTOP",
    "desktop": "DESKTOP",
}
# asset.type -> DeviceTypeStr member name
ASSET_TYPE_MAP: dict[str, str] = {
    "guest": "VIRTUAL",
    "hypervisor": "VIRTUAL",
    "mobile": "MOBILE",
}

_TAG_RE = re.compile(r"<[^>]+>")
_SPACES_RE = re.compile(r"\s+")


# --- dates ---------------------------------------------------------------------------


def parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp; ``None`` when absent or malformed.

    A date without a timezone is read as UTC, so every parsed value can be compared.
    """
    if not value:
        return None
    try:
        parsed = isoparse(value)
    except (ValueError, OverflowError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def to_epoch(value: str | None) -> float | None:
    parsed = parse_datetime(value)
    return parsed.timestamp() if parsed is not None else None


def to_int_epoch(value: str | None) -> int | None:
    epoch = to_epoch(value)
    return int(epoch) if epoch is not None else None


def last_assessed(asset: Rapid7Asset) -> str | None:
    """Return the raw timestamp of the latest assessment event of the asset history."""
    latest_raw: str | None = None
    latest_dt: datetime | None = None
    for event in asset.history:
        if (event.type or "").upper() not in ASSESSMENT_EVENT_TYPES:
            continue
        event_dt = parse_datetime(event.date)
        if event_dt is not None and (latest_dt is None or event_dt > latest_dt):
            latest_dt, latest_raw = event_dt, event.date
    return latest_raw


def first_seen(finding: Rapid7Finding | None) -> int | None:
    """``finding.since``, falling back to the earliest ``results[].since``."""
    if finding is None:
        return None
    if (since := to_int_epoch(finding.since)) is not None:
        return since
    candidates = [epoch for epoch in (to_int_epoch(result.since) for result in finding.results) if epoch is not None]
    return min(candidates) if candidates else None


def latest_reintroduction(finding: Rapid7Finding) -> datetime | None:
    dates = [d for d in (parse_datetime(result.reintroduced) for result in finding.results) if d is not None]
    return max(dates) if dates else None


def latest_change(finding: Rapid7Finding) -> datetime | None:
    """Latest of ``since``, ``results[].since`` and ``results[].reintroduced``."""
    values = [finding.since]
    for result in finding.results:
        values.extend((result.since, result.reintroduced))
    dates = [d for d in (parse_datetime(value) for value in values) if d is not None]
    return max(dates) if dates else None


# --- text ------------------------------------------------------------------------------


def strip_html(value: str | None) -> str | None:
    """Remove the HTML tags and entities of an InsightVM text and collapse whitespace."""
    if value is None:
        return None
    text = _SPACES_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", value))).strip()
    return text or None


def truncate(value: str | None, limit: int = MAX_DESC_LENGTH, suffix: str = TRUNCATION_SUFFIX) -> str | None:
    """Trim a text to ``limit`` characters, ending it with ``suffix`` when it is shortened."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) <= limit:
        return trimmed
    if len(suffix) >= limit:
        return trimmed[:limit]
    return trimmed[: limit - len(suffix)] + suffix


# --- vulnerability definition ---------------------------------------------------------------


def cvss_version(vector: str | None) -> str:
    """Read the CVSS 3.x version from the vector prefix (``CVSS:3.1/...``); "3.0" by default."""
    if vector and vector.upper().startswith("CVSS:"):
        version = vector.split("/", 1)[0].split(":", 1)[1].strip()
        if version:
            return version
    return "3.0"


def summarize_vulnerability(vulnerability: Rapid7Vulnerability) -> VulnerabilitySummary:
    """Keep only the mapped subset of a definition, with a plain and truncated description."""
    description = vulnerability.description
    text = None
    if description is not None:
        text = strip_html(description.text) or strip_html(description.html)

    cvss = vulnerability.cvss
    v2 = cvss.v2 if cvss else None
    v3 = cvss.v3 if cvss else None

    return VulnerabilitySummary(
        id=vulnerability.id,
        title=vulnerability.title,
        desc=truncate(text),
        cves=[cve.strip() for cve in vulnerability.cves if cve and cve.strip()],
        cvss_v2_score=v2.score if v2 else None,
        cvss_v3_score=v3.score if v3 else None,
        cvss_v3_version=cvss_version(v3.vector) if v3 and v3.score is not None else None,
        severity=vulnerability.severity,
        risk_score=vulnerability.riskScore,
        fix_available=vulnerability.fixAvailable,
        categories=[category for category in vulnerability.categories if category],
        added=vulnerability.added,
    )


def map_severity(severity: str | None) -> tuple[Severity, int]:
    if not severity:
        return UNKNOWN_SEVERITY
    return SEVERITY_MAP.get(severity.strip().lower(), UNKNOWN_SEVERITY)


def map_risk_level(severity: str | None) -> tuple[RiskLevelStr | None, RiskLevelId | None]:
    member = RISK_LEVEL_MAP.get((severity or "").strip().lower())
    if member is None:
        return None, None
    return RiskLevelStr[member], RiskLevelId[member]


def to_risk_score(risk_score: float | None) -> int | None:
    return int(round(risk_score)) if risk_score is not None else None


def map_confidence(results: list[Rapid7FindingResult]) -> tuple[str | None, int | None]:
    """The best confidence among the result statuses of a finding."""
    best: tuple[str, int] | None = None
    for result in results:
        status = (result.status or "").strip().lower().removesuffix(EXCEPTION_SUFFIX)
        confidence = CONFIDENCE_MAP.get(status)
        if confidence is not None and (best is None or confidence[1] > best[1]):
            best = confidence
    return best if best is not None else (None, None)


def build_risk_details(results: list[Rapid7FindingResult]) -> str | None:
    """Join the proofs of the results as ``<protocol>/<port>: <proof>``."""
    parts: list[str] = []
    for result in results:
        proof = strip_html(result.proof)
        if not proof:
            continue
        if result.port is not None:
            proof = f"{(result.protocol or '').lower() or 'port'}/{result.port}: {proof}"
        parts.append(proof)
    return truncate(" | ".join(parts)) if parts else None


def date_to_int_epoch(value: str | None) -> int | None:
    """Convert a ``YYYY-MM-DD`` date (or an ISO timestamp) to an epoch at 00:00 UTC."""
    return to_int_epoch(value)


def build_src_url(base_url: str, vuln_id: str) -> str:
    return f"{base_url}{VULNERABILITY_PAGE.format(vuln_id=quote(vuln_id, safe=''))}"


def build_references(cves: list[str], src_url: str | None) -> list[str] | None:
    """NVD URL of every CVE plus the console page, bounded to the API limits."""
    candidates = [NVD_URL.format(cve=cve) for cve in cves]
    if src_url:
        candidates.append(src_url)

    references: list[str] = []
    for candidate in candidates:
        reference = candidate.strip()[:MAX_REFERENCE_LENGTH]
        if reference and reference not in references:
            references.append(reference)
        if len(references) >= MAX_REFERENCES:
            break
    return references or None


def build_cvss(definition: VulnerabilitySummary | None) -> list[CVSS] | None:
    if definition is None:
        return None
    cvss: list[CVSS] = []
    if definition.cvss_v2_score is not None:
        cvss.append(CVSS(version="2.0", base_score=float(definition.cvss_v2_score)))
    if definition.cvss_v3_score is not None:
        cvss.append(CVSS(version=definition.cvss_v3_version or "3.0", base_score=float(definition.cvss_v3_score)))
    return cvss or None


def build_vulnerabilities(
    definition: VulnerabilitySummary | None, severity: str, src_url: str | None
) -> list[VulnerabilityDetails]:
    """One ``VulnerabilityDetails`` per CVE, or a single one without CVE."""
    title = definition.title if definition else None
    desc = definition.desc if definition else None
    is_fix_available = definition.fix_available if definition else None
    cves = definition.cves if definition else []
    references = build_references(cves, src_url)
    cvss = build_cvss(definition)

    details = [
        VulnerabilityDetails(
            cve=CVE(uid=cve, type="CVE", cvss=cvss, desc=desc, title=title),
            title=title,
            desc=desc,
            references=references,
            severity=severity,
            vendor_name=VENDOR_NAME,
            is_fix_available=is_fix_available,
        )
        for cve in cves
    ]
    if not details:
        details.append(
            VulnerabilityDetails(
                title=title,
                desc=desc,
                references=references,
                severity=severity,
                vendor_name=VENDOR_NAME,
                is_fix_available=is_fix_available,
            )
        )
    return details


def build_product() -> Product:
    return Product(name=PRODUCT_NAME, vendor_name=VENDOR_NAME)


# --- device ------------------------------------------------------------------------------


def map_device_type(asset: Rapid7Asset) -> tuple[DeviceTypeStr, DeviceTypeId]:
    """``osFingerprint.type`` (Server, Workstation) first, then ``asset.type`` (guest, mobile)."""
    fingerprint_type = (asset.osFingerprint.type if asset.osFingerprint else None) or ""
    member = FINGERPRINT_TYPE_MAP.get(fingerprint_type.strip().lower()) or ASSET_TYPE_MAP.get(
        (asset.type or "").strip().lower()
    )
    if member is None:
        return DeviceTypeStr.UNKNOWN, DeviceTypeId.UNKNOWN
    return DeviceTypeStr[member], DeviceTypeId[member]


def map_os_type(family: str | None, system_name: str | None, vendor: str | None) -> tuple[OSTypeStr, OSTypeId]:
    """Map the OS family (then the system name) to an OCSF OS type.

    Cisco names its network OS "IOS": it is not Apple iOS, so it maps to Other.
    """
    if not family and not system_name:
        return OSTypeStr.UNKNOWN, OSTypeId.UNKNOWN

    is_cisco = "cisco" in f"{vendor or ''} {system_name or ''}".lower()
    for value in (family, system_name):
        lowered = (value or "").strip().lower()
        if not lowered:
            continue
        for keyword, member in OS_KEYWORDS:
            if keyword in lowered:
                if member == "IOS" and is_cisco:
                    return OSTypeStr.OTHER, OSTypeId.OTHER
                return OSTypeStr[member], OSTypeId[member]
    return OSTypeStr.OTHER, OSTypeId.OTHER


def build_operating_system(asset: Rapid7Asset) -> OperatingSystem | None:
    fingerprint = asset.osFingerprint
    name = (fingerprint.description if fingerprint else None) or asset.os
    family = fingerprint.family if fingerprint else None
    system_name = fingerprint.systemName if fingerprint else None
    if not name and not family and not system_name:
        return None
    os_type, os_type_id = map_os_type(family, system_name, fingerprint.vendor if fingerprint else None)
    return OperatingSystem(name=name, type=os_type, type_id=os_type_id)


def device_hostname(asset: Rapid7Asset) -> str:
    """``hostName``, then the first named ``hostNames`` entry, then the IP; empty otherwise."""
    if asset.hostName:
        return asset.hostName
    for host_name in asset.hostNames:
        if host_name.name:
            return host_name.name
    return asset.ip or ""


def build_device(asset: Rapid7Asset) -> Device:
    device_type, device_type_id = map_device_type(asset)
    return Device(
        uid=asset.id,
        hostname=device_hostname(asset),
        type=device_type,
        type_id=device_type_id,
        ip=asset.ip,
        os=build_operating_system(asset),
    )
