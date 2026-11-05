from dataclasses import dataclass, field
from enum import Enum

from rapid7_insightvm.asset_connector.models import Rapid7Asset, Rapid7Finding, VulnerabilitySummary

# AssetVulnerabilityResultSummary.status of the InsightVM v4 API
OPEN_STATUSES = frozenset({"VULNERABLE_EXPL", "VULNERABLE_VERS", "VULNERABLE_POTENTIAL"})
CLOSING_STATUSES = frozenset(
    {
        "NOT_VULNERABLE",
        "NOT_VULN_DONT_STORE",
        "EXCEPTION_VULN_EXPL",
        "EXCEPTION_VULN_VERS",
        "EXCEPTION_VULN_POTL",
        "OVERRIDDEN_VULN_VERS",
        "SUPERSEDED",
    }
)
# Inconclusive: UNKNOWN, SKIPPED_VERS, SKIPPED_DOS, SKIPPED_DISABLED, UNEXPECTED_ERR and any unrecognised value
# (except an unknown status starting with VULNERABLE, which is open).
OPEN_PREFIX = "VULNERABLE"

FindingActivity = tuple[int, str, int]
CREATE: FindingActivity = (1, "Create", 200201)
UPDATE: FindingActivity = (2, "Update", 200202)
CLOSE: FindingActivity = (3, "Close", 200203)


class State(Enum):
    """The state of a vulnerability on an asset, from the statuses of its instances."""

    OPEN = "open"
    CLOSED = "closed"
    INCONCLUSIVE = "inconclusive"


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


def normalise_status(status: str | None) -> str:
    return (status or "").strip().upper()


def is_vulnerable(status: str | None) -> bool:
    """Whether a finding status means the vulnerability is present (without exception).

    An unknown status starting with ``VULNERABLE`` is open (see ``is_unknown_open_status``).
    """
    return normalise_status(status).startswith(OPEN_PREFIX)


def is_unknown_open_status(status: str | None) -> bool:
    """An open status the connector does not know: counted as open, worth a warning."""
    return is_vulnerable(status) and normalise_status(status) not in OPEN_STATUSES


def is_closing(status: str | None) -> bool:
    """Whether a finding status confirms that the vulnerability is absent or accepted."""
    return normalise_status(status) in CLOSING_STATUSES


def state_of(findings: list[Rapid7Finding]) -> State | None:
    """The state of a vulnerability from its instances; ``None`` without instance.

    Open if any instance is open. Otherwise closed only if at least one instance is closing
    and none is inconclusive (check skipped or failed). Otherwise inconclusive.
    """
    if not findings:
        return None
    if any(is_vulnerable(finding.status) for finding in findings):
        return State.OPEN
    if all(is_closing(finding.status) for finding in findings):
        return State.CLOSED
    return State.INCONCLUSIVE


def current_state(delta: VulnerabilityDelta) -> State | None:
    """The state at the end of the window: the ``same`` and ``new`` instances."""
    return state_of(delta.same + delta.new)


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
    return frozenset(normalise_status(finding.status) for finding in findings)


def _instance_set(findings: list[Rapid7Finding]) -> frozenset[tuple[int | None, str, str]]:
    """The affected instances: ``(port, protocol, key)`` of each finding."""
    return frozenset(
        (finding.port, (finding.protocol or "").strip().upper(), finding.key or "") for finding in findings
    )


def _is_inconclusive(finding: Rapid7Finding) -> bool:
    return not is_vulnerable(finding.status) and not is_closing(finding.status)


def detect_change(
    delta: VulnerabilityDelta, first_run: bool, full_resync: bool = False
) -> tuple[FindingActivity, list[Rapid7Finding]] | None:
    """The activity of a vulnerability on an asset over the window, with the findings it is built from.

    An inconclusive current state (check skipped or failed) emits nothing. A vulnerability closed
    after an inconclusive state is closed, since the window that made it inconclusive emitted nothing:
    the Close may reach a finding the platform does not know, which is harmless. An open vulnerability
    whose statuses or affected instances (port, protocol, key) change is updated. With ``full_resync``
    (after a checkpoint reset), a vulnerability still open and unchanged is emitted again as Update.
    """
    state = current_state(delta)
    if state is State.INCONCLUSIVE:
        return None

    vulnerable_now = _vulnerable_instances(delta.same + delta.new)
    if first_run:
        return (CREATE, vulnerable_now) if vulnerable_now else None

    before = delta.same + delta.remediated
    vulnerable_before = _vulnerable_instances(before)
    if vulnerable_now and not vulnerable_before:
        if any(finding.reintroduced for finding in _vulnerable_instances(delta.new)):
            return UPDATE, vulnerable_now
        return CREATE, vulnerable_now
    if vulnerable_before and not vulnerable_now:
        return CLOSE, vulnerable_before
    if state is State.CLOSED and not vulnerable_before and any(_is_inconclusive(finding) for finding in before):
        # open -> inconclusive -> closed: the Close was held back while the state was inconclusive
        return CLOSE, before
    if vulnerable_now and (
        full_resync
        or _status_set(vulnerable_before) != _status_set(vulnerable_now)
        or _instance_set(vulnerable_before) != _instance_set(vulnerable_now)
    ):
        return UPDATE, vulnerable_now
    return None
