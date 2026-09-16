from dataclasses import dataclass
from enum import StrEnum


class MoknThreatLevel(StrEnum):
    """Supported MokN threat levels used for filtering."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True)
class AttemptQuery:
    """Describe the filters applied when listing MokN login attempts."""

    page_size: int
    statuses: list[int]
    threat_levels: list[MoknThreatLevel]
    pending: bool
