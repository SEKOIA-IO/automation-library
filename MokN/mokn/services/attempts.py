from datetime import datetime
from typing import Any

from mokn.domain import (
    AttemptDetail,
    AttemptQuery,
    AttemptSummary,
    NormalizedAttack,
    NormalizedAttempt,
)
from mokn.repositories import AttemptRepository


class AttemptService:
    """Handle MokN attempt business logic and normalization."""

    def __init__(self, repository: AttemptRepository):
        """Create a service backed by the MokN attempt repository."""

        self.repository = repository

    def list_attempt_summaries(self, start: datetime, query: AttemptQuery) -> list[AttemptSummary]:
        """List summarized attempts for connector polling."""

        return self.repository.list_attempts(start, query)

    def get_attempt_detail(self, attempt_id: int) -> AttemptDetail:
        """Fetch the detailed payload for a single attempt."""

        return self.repository.get_attempt_detail(attempt_id)

    def comment_attempt(self, attempt_id: int, comment: str) -> dict[str, Any]:
        """Update the comment attached to an attempt."""

        return self.repository.comment_attempt(attempt_id, comment)

    def request_credential_check(self, attempt_id: int) -> dict[str, Any]:
        """Ask MokN to run a credential check for an attempt."""

        return self.repository.request_credential_check(attempt_id)

    def normalize_attempt(self, summary: AttemptSummary, detail: AttemptDetail) -> NormalizedAttempt:
        """Merge summary and detail payloads into the public event format."""

        summary_payload = self._select_summary_attributes(summary.raw)
        detail_payload = detail.raw
        attack_payload = self._build_attack(summary.raw, detail_payload)

        return NormalizedAttempt(
            attributes=summary_payload,
            attack=NormalizedAttack(payload=attack_payload),
            credential_checks=detail_payload.get("credential_checks", []),
            leaks=detail_payload.get("leaks", []),
        )

    @staticmethod
    def _select_summary_attributes(summary: dict[str, Any]) -> dict[str, Any]:
        """Keep only the summary fields that are meant to be public."""

        ignored_keys = {
            "ip",
            "country",
            "country_code",
            "has_leaked",
            "policy_mismatch",
            "has_sprayed",
            "is_empty",
            "is_whitelist",
            "is_ip_whitelist",
            "has_variations",
            "has_alerted",
            "has_bruteforce",
            "is_opportunist",
            "is_ip_opportunist",
            "is_agent_available",
            "agent_id",
            "agent_name",
            "whitelist_type",
        }
        return {key: value for key, value in summary.items() if key not in ignored_keys}

    @staticmethod
    def _build_attack(summary: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
        """Build the public attack payload from detail data and safe fallbacks."""

        attack = dict(detail.get("attack", {}))
        attacker_profile = detail.get("attacker_profile", {})

        if summary.get("ip") and not attack.get("ip"):
            attack["ip"] = summary["ip"]
        if summary.get("country") and not attack.get("country"):
            attack["country"] = summary["country"]
        if summary.get("country_code") and not attack.get("country_code"):
            attack["country_code"] = summary["country_code"]
        if attacker_profile.get("reputation") and not attack.get("reputation"):
            attack["reputation"] = attacker_profile["reputation"]
        if attacker_profile.get("total_attempts") is not None and not attack.get("total_attempts"):
            attack["total_attempts"] = attacker_profile["total_attempts"]
        if attacker_profile.get("total_targeted_attempts") is not None and not attack.get("total_targeted_attempts"):
            attack["total_targeted_attempts"] = attacker_profile["total_targeted_attempts"]

        for duplicated_key in ("bait", "date", "threat_level", "username", "password"):
            attack.pop(duplicated_key, None)

        return attack
