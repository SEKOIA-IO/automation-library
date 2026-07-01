from datetime import UTC, datetime
from unittest.mock import Mock

from mokn.domain import AttemptDetail, AttemptQuery, AttemptSummary, MoknThreatLevel
from mokn.services import AttemptService


def test_list_attempt_summaries_delegates_to_repository():
    repository = Mock()
    service = AttemptService(repository=repository)
    query = AttemptQuery(
        page_size=10,
        statuses=[1],
        threat_levels=[MoknThreatLevel.HIGH],
        pending=True,
    )
    start = datetime(2026, 4, 23, 8, 0, 0, tzinfo=UTC)

    service.list_attempt_summaries(start, query)

    repository.list_attempts.assert_called_once_with(start, query)


def test_get_attempt_detail_delegates_to_repository():
    repository = Mock()
    service = AttemptService(repository=repository)

    service.get_attempt_detail(42)

    repository.get_attempt_detail.assert_called_once_with(42)


def test_comment_attempt_delegates_to_repository():
    repository = Mock()
    service = AttemptService(repository=repository)

    service.comment_attempt(42, "needs triage")

    repository.comment_attempt.assert_called_once_with(42, "needs triage")


def test_request_credential_check_delegates_to_repository():
    repository = Mock()
    service = AttemptService(repository=repository)

    service.request_credential_check(42)

    repository.request_credential_check.assert_called_once_with(42)


def test_normalize_attempt_merges_summary_and_detail_payloads():
    service = AttemptService(repository=Mock())
    summary = AttemptSummary(
        attempt_id=1,
        updated_time=datetime(2026, 4, 14, 12, 45, 54, tzinfo=UTC),
        raw={
            "id": 1,
            "date": "2026-04-14T12:45:54+00:00",
            "updated_time": "2026-04-14T12:45:54+00:00",
            "bait_name": "App Portal",
            "username": "user-3",
            "password": "password-example-3",
            "is_targeted": True,
            "comment": "",
            "type": "Targeted",
            "identification": "App Connector",
            "status": 9,
            "threat_level": "LOW",
            "ip": "82.67.33.112",
            "country": "France",
            "country_code": "FR",
        },
    )
    detail = AttemptDetail(
        attempt_id=1,
        raw={
            "attack": {
                "ip": "127.0.0.1",
                "country": "Germany",
                "country_code": "DE",
                "username": "hidden-user",
                "password": "hidden-password",
                "ja4h": "sample-ja4h",
                "user_agent": "GenericBrowser/1.0",
                "headers": [
                    ["Host", "app"],
                    ["Origin", "https://app"],
                    ["Referer", "https://app/login"],
                    ["X-Forwarded-For", "127.0.0.1"],
                ],
                "date": "2026-03-18T05:11:51+00:00",
                "bait": "App Portal",
                "threat_level": "MEDIUM",
                "opportunistic_patterns": [
                    {"name": "has_leaked", "threat_level_setting": "HIGH"},
                ],
            },
            "credential_checks": [],
            "leaks": [
                {
                    "site": "random_source_a.txt",
                    "date": "2024-07-18T00:00:00+00:00",
                },
                {
                    "site": "random_source_b.zip",
                    "date": "2023-11-02T00:00:00+00:00",
                },
            ],
            "attacker_profile": {
                "reputation": "Malicious",
                "total_attempts": 12,
                "total_targeted_attempts": 12,
            },
        },
    )

    normalized = service.normalize_attempt(summary, detail).to_dict()

    assert normalized == {
        "id": 1,
        "date": "2026-04-14T12:45:54+00:00",
        "updated_time": "2026-04-14T12:45:54+00:00",
        "bait_name": "App Portal",
        "username": "user-3",
        "password": "password-example-3",
        "is_targeted": True,
        "comment": "",
        "type": "Targeted",
        "identification": "App Connector",
        "status": 9,
        "threat_level": "LOW",
        "attack": {
            "ip": "127.0.0.1",
            "country": "Germany",
            "country_code": "DE",
            "ja4h": "sample-ja4h",
            "user_agent": "GenericBrowser/1.0",
            "headers": [
                ["Host", "app"],
                ["Origin", "https://app"],
                ["Referer", "https://app/login"],
                ["X-Forwarded-For", "127.0.0.1"],
            ],
            "opportunistic_patterns": [
                {"name": "has_leaked", "threat_level_setting": "HIGH"},
            ],
            "reputation": "Malicious",
            "total_attempts": 12,
            "total_targeted_attempts": 12,
        },
        "leaks": [
            {"site": "random_source_a.txt", "date": "2024-07-18T00:00:00+00:00"},
            {"site": "random_source_b.zip", "date": "2023-11-02T00:00:00+00:00"},
        ],
    }


def test_normalize_attempt_preserves_existing_attack_fields():
    service = AttemptService(repository=Mock())
    summary = AttemptSummary(
        attempt_id=7,
        updated_time=datetime(2026, 4, 23, 8, 9, 10, tzinfo=UTC),
        raw={"ip": "1.2.3.4", "country": "France", "country_code": "FR"},
    )
    detail = AttemptDetail(
        attempt_id=7,
        raw={"attack": {"ip": "8.8.8.8", "country": "Germany", "country_code": "DE"}},
    )

    normalized = service.normalize_attempt(summary, detail)

    assert normalized.attack.to_dict() == {
        "ip": "8.8.8.8",
        "country": "Germany",
        "country_code": "DE",
    }
