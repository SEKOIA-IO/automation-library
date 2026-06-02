from datetime import UTC, datetime
from unittest.mock import Mock

from mokn.domain import AttemptQuery, AttemptSummary, MoknThreatLevel
from mokn.repositories import AttemptRepository


def make_repository() -> AttemptRepository:
    return AttemptRepository(client=Mock(base_url="https://mokn.example"), verify_ssl=False)


def test_parse_datetime_normalizes_zulu_timezone():
    parsed = AttemptRepository.parse_datetime("2026-04-23T08:09:10.123Z")

    assert parsed == datetime(2026, 4, 23, 8, 9, 10, 123000, tzinfo=UTC)


def test_to_mokn_datetime_serializes_to_milliseconds_zulu():
    value = datetime(2026, 4, 23, 8, 9, 10, 123456, tzinfo=UTC)

    assert AttemptRepository.to_mokn_datetime(value) == "2026-04-23T08:09:10.123Z"


def test_build_filters_uses_query_parameters():
    repository = make_repository()
    query = AttemptQuery(
        page_size=50,
        statuses=[1, 4],
        threat_levels=[MoknThreatLevel.HIGH, MoknThreatLevel.MEDIUM],
        pending=True,
    )

    filters = repository.build_filters(datetime(2026, 4, 23, 8, 9, 10, tzinfo=UTC), query)

    assert filters == {
        "filters": {
            "global_operator": "and",
            "filters": [
                {"id": "status", "values": [1, 4], "operator": "equals"},
                {
                    "id": "datetime_from",
                    "values": "2026-04-23T08:09:10.000Z",
                    "operator": "equals",
                },
                {
                    "id": "type",
                    "values": ["HIGH", "MEDIUM"],
                    "operator": "equals",
                },
            ],
            "pending": True,
        }
    }


def test_list_attempts_calls_api_and_maps_results():
    repository = make_repository()
    post_response = {
        "status": "success",
        "message": "Attempts successfully retrieved.",
        "data": {
            "results": [
                {
                    "id": 2,
                    "date": "2026-04-23T05:13:43+00:00",
                    "updated_time": "2026-04-23T05:13:44+00:00",
                    "bait_name": "App Portal",
                    "username": "user-alpha",
                    "password": "password-alpha",
                    "is_targeted": False,
                    "comment": "",
                    "type": "Bots",
                    "identification": "",
                    "status": 5,
                    "threat_level": "LOW",
                },
                {
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
                },
            ]
        },
    }
    repository.request = Mock(return_value=post_response)
    query = AttemptQuery(
        page_size=25,
        statuses=[1],
        threat_levels=[MoknThreatLevel.HIGH],
        pending=False,
    )

    results = repository.list_attempts(datetime(2026, 4, 23, 8, 0, 0, tzinfo=UTC), query)

    assert results == [
        AttemptSummary(
            attempt_id=2,
            updated_time=datetime(2026, 4, 23, 5, 13, 44, tzinfo=UTC),
            raw=post_response["data"]["results"][0],
        ),
        AttemptSummary(
            attempt_id=1,
            updated_time=datetime(2026, 4, 14, 12, 45, 54, tzinfo=UTC),
            raw=post_response["data"]["results"][1],
        ),
    ]
    repository.request.assert_called_once_with(
        "POST",
        "https://mokn.example/api/v1/baits/logins",
        json_body=repository.build_filters(datetime(2026, 4, 23, 8, 0, 0, tzinfo=UTC), query),
        params={"page": 1, "pageSize": 25},
    )


def test_get_attempt_detail_returns_mapped_detail():
    repository = make_repository()
    get_response = {
        "status": "success",
        "message": "Attempts successfully retrieved.",
        "data": {
            "attack": {
                "ip": "127.0.0.1",
                "country": "Germany",
                "country_code": "DE",
                "ja4h": "sample-ja4h",
                "user_agent": "GenericBrowser/1.0",
                "headers": [["Host", "app"]],
                "date": "2026-03-18T05:11:51+00:00",
                "bait": "App Portal",
                "threat_level": "MEDIUM",
            },
            "credential_checks": [],
            "leaks": [],
            "comment": None,
        },
    }
    repository.request = Mock(return_value=get_response)

    detail = repository.get_attempt_detail(1)

    assert detail.attempt_id == 1
    assert detail.raw == get_response["data"]
    repository.request.assert_called_once_with(
        "GET",
        "https://mokn.example/api/v1/baits/logins/1",
    )


def test_comment_attempt_calls_update_endpoint():
    repository = make_repository()
    repository.request = Mock(
        return_value={
            "status": "success",
            "message": "Login Attempt successfully updated.",
            "data": {
                "id": 42,
                "comment": "needs triage",
            },
        }
    )

    payload = repository.comment_attempt(42, "needs triage")

    assert payload["status"] == "success"
    assert payload["message"] == "Login Attempt successfully updated."
    assert payload["data"]["id"] == 42
    repository.request.assert_called_once_with(
        "PUT",
        "https://mokn.example/api/v1/baits/logins/42",
        json_body={"comment": "needs triage"},
    )


def test_request_credential_check_calls_update_endpoint():
    repository = make_repository()
    repository.request = Mock(
        return_value={
            "status": "success",
            "message": "Login Attempt successfully updated.",
            "data": {
                "id": 42,
            },
        }
    )

    payload = repository.request_credential_check(42)

    assert payload["status"] == "success"
    assert payload["message"] == "Login Attempt successfully updated."
    assert payload["data"]["id"] == 42
    repository.request.assert_called_once_with(
        "PUT",
        "https://mokn.example/api/v1/baits/logins/42",
        json_body={"status": -2},
    )
