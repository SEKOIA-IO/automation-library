from datetime import UTC, datetime

from mokn.domain import (
    AttemptDetail,
    AttemptSummary,
    NormalizedAttack,
    NormalizedAttempt,
)


def test_attempt_summary_second_truncates_microseconds():
    summary = AttemptSummary(
        attempt_id=42,
        updated_time=datetime(2026, 4, 23, 10, 11, 12, 987654, tzinfo=UTC),
        raw={},
    )

    assert summary.second == datetime(2026, 4, 23, 10, 11, 12, tzinfo=UTC)


def test_normalized_attack_to_dict_returns_copy():
    attack = NormalizedAttack(payload={"ip": "1.2.3.4"})

    payload = attack.to_dict()
    payload["ip"] = "9.9.9.9"

    assert attack.payload == {"ip": "1.2.3.4"}


def test_normalized_attempt_to_dict_keeps_optional_sections_only_when_present():
    attempt = NormalizedAttempt(
        attributes={"attempt_id": 7},
        attack=NormalizedAttack(payload={"ip": "1.2.3.4"}),
        credential_checks=[{"provider": "ok"}],
        leaks=[],
    )

    assert attempt.to_dict() == {
        "attempt_id": 7,
        "attack": {"ip": "1.2.3.4"},
        "credential_checks": [{"provider": "ok"}],
    }


def test_attempt_detail_keeps_raw_payload():
    detail = AttemptDetail(attempt_id=10, raw={"attack": {"ip": "1.1.1.1"}})

    assert detail.attempt_id == 10
    assert detail.raw["attack"]["ip"] == "1.1.1.1"
