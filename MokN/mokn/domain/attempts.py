from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AttemptCursor:
    """Track the polling second and IDs already processed within it."""

    second: datetime
    seen_ids: set[int] = field(default_factory=set)


@dataclass(frozen=True)
class AttemptSummary:
    """Represent a summarized login attempt returned by the listing endpoint."""

    attempt_id: int
    updated_time: datetime
    raw: dict[str, Any]

    @property
    def second(self) -> datetime:
        """Return the update timestamp truncated to second precision."""

        return self.updated_time.replace(microsecond=0)


@dataclass(frozen=True)
class AttemptDetail:
    """Represent the detailed payload returned for a single attempt."""

    attempt_id: int
    raw: dict[str, Any]


@dataclass(frozen=True)
class NormalizedAttack:
    """Store the normalized attack subdocument exposed to downstream users."""

    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a copy of the normalized attack payload."""

        return dict(self.payload)


@dataclass(frozen=True)
class NormalizedAttempt:
    """Store the normalized event payload emitted by the connector."""

    attributes: dict[str, Any]
    attack: NormalizedAttack
    credential_checks: list[dict[str, Any]]
    leaks: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized attempt and omit empty optional sections."""

        payload = dict(self.attributes)
        payload["attack"] = self.attack.to_dict()
        if self.credential_checks:
            payload["credential_checks"] = list(self.credential_checks)
        if self.leaks:
            payload["leaks"] = list(self.leaks)
        return payload
