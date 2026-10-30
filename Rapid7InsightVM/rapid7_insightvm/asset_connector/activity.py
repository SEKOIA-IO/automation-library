from dataclasses import dataclass, field

from rapid7_insightvm.asset_connector.models import Rapid7Asset, Rapid7Finding, VulnerabilitySummary


VULNERABLE_STATUSES = frozenset({"VULNERABLE_EXPL", "VULNERABLE_VERS", "VULNERABLE_POTENTIAL"})

FindingActivity = tuple[int, str, int]
CREATE: FindingActivity = (1, "Create", 200201)
UPDATE: FindingActivity = (2, "Update", 200202)
CLOSE: FindingActivity = (3, "Close", 200203)


@dataclass
class VulnerabilityDelta:
    """The findings of one vulnerability on one asset, split by delta list."""

    new: list[Rapid7Finding] = field(default_factory=list)
    same: list[Rapid7Finding] = field(default_factory=list)
    remediated: list[Rapid7Finding] = field(default_factory=list)


@dataclass
class VulnerabilityChange:
    """A vulnerability whose state changed on an asset: what the mapper turns into a Vulnerability Finding."""

    id: str
    activity: FindingActivity
    findings: list[Rapid7Finding]
    definition: VulnerabilitySummary | None = None
    asset_last_assessed: str | None = None
    window_end: str | None = None


def is_vulnerable(status: str | None) -> bool:
    """Whether a finding status means the vulnerability is present (without exception)."""
    return (status or "").strip().upper() in VULNERABLE_STATUSES


def split_by_vulnerability(asset: Rapid7Asset) -> dict[str, VulnerabilityDelta]:
    """Group the ``new``, ``same`` and ``remediated`` items of an asset by vulnerability id"""
    deltas: dict[str, VulnerabilityDelta] = {}
    for bucket in ("new", "same", "remediated"):
        for finding in getattr(asset, bucket):
            delta = deltas.setdefault(finding.vulnerability_id, VulnerabilityDelta())
            getattr(delta, bucket).append(finding)
    return deltas


def _vulnerable_instances(findings: list[Rapid7Finding]) -> list[Rapid7Finding]:
    return [finding for finding in findings if is_vulnerable(finding.status)]


def _status_set(findings: list[Rapid7Finding]) -> frozenset[str]:
    return frozenset((finding.status or "").strip().upper() for finding in findings)


def detect_change(delta: VulnerabilityDelta, first_run: bool) -> tuple[FindingActivity, list[Rapid7Finding]] | None:
    vulnerable_now = _vulnerable_instances(delta.same + delta.new)
    if first_run:
        return (CREATE, vulnerable_now) if vulnerable_now else None

    vulnerable_before = _vulnerable_instances(delta.same + delta.remediated)
    if vulnerable_now and not vulnerable_before:
        if any(finding.reintroduced for finding in _vulnerable_instances(delta.new)):
            return UPDATE, vulnerable_now
        return CREATE, vulnerable_now
    if vulnerable_before and not vulnerable_now:
        return CLOSE, vulnerable_before
    if vulnerable_before and vulnerable_now and _status_set(vulnerable_before) != _status_set(vulnerable_now):
        return UPDATE, vulnerable_now
    return None
