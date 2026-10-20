from unittest.mock import ANY, Mock, call, patch

import orjson
import pytest
import requests_mock
from freezegun import freeze_time
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError

from cortex_module.cortex_edr_connector import CortexQueryEDRTrigger
from cortex_module.helper import handle_fqdn


@pytest.fixture
def trigger(module, symphony_storage):
    trigger = CortexQueryEDRTrigger(module=module, data_path=symphony_storage)
    trigger.configuration = {
        "frequency": 604800,
        "tenant_id": "4feff6df-7454-4036-923d-7b2444462416",
        "chunk_size": 2,
        "intake_key": "0123456789",
    }

    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()
    return trigger


@pytest.fixture
def issue_query_2():
    return {
        "request_data": {
            "filters": [{"field": "modification_time", "operator": "gte", "value": 1706003700000}],
            "search_from": 0,
            "search_to": 2,
            "sort": {"field": "modification_time", "keyword": "desc"},
        }
    }


@pytest.fixture
def issue_query_4():
    return {
        "request_data": {
            "filters": [{"field": "modification_time", "operator": "gte", "value": 1706003700000}],
            "search_from": 2,
            "search_to": 4,
            "sort": {"field": "modification_time", "keyword": "desc"},
        }
    }


@pytest.fixture
def issue_response_2():
    return {
        "reply": {
            "total_count": 2,
            "result_count": 2,
            "issues": [
                {
                    "issue_id": "5930923",
                    "severity": "MEDIUM",
                    "modification_time": 1705912900118,
                    "is_excluded": False,
                },
                {
                    "issue_id": "1",
                    "severity": "MEDIUM",
                    "modification_time": 1705912686000,
                    "is_excluded": False,
                },
            ],
        }
    }


@pytest.fixture
def issue_response_3_2():
    return {
        "reply": {
            "total_count": 3,
            "result_count": 2,
            "issues": [
                {
                    "issue_id": "5930923",
                    "severity": "MEDIUM",
                    "modification_time": 1705912900118,
                    "is_excluded": False,
                },
                {
                    "issue_id": "1",
                    "severity": "MEDIUM",
                    "modification_time": 1705912686000,
                    "is_excluded": False,
                },
            ],
        }
    }


@pytest.fixture
def issue_response_3_1():
    return {
        "reply": {
            "total_count": 3,
            "result_count": 1,
            "issues": [
                {
                    "issue_id": "2",
                    "severity": "LOW",
                    "modification_time": 1705912200000,
                    "is_excluded": True,
                },
            ],
        }
    }


@pytest.fixture
def issue_response_0():
    return {"reply": {"total_count": 0, "result_count": 0, "issues": []}}


@pytest.fixture
def issue_response_empty():
    return {"reply": {"total_count": 0, "result_count": 0, "issues": None}}


def test_handle_fqdn():
    assert (
        handle_fqdn("https://api-XXXX.test.paloaltonetworks.com")
        == "https://api-XXXX.test.paloaltonetworks.com/public_api/v1/issue/search"
    )
    assert (
        handle_fqdn("api-XXXX.test.paloaltonetworks.com")
        == "https://api-XXXX.test.paloaltonetworks.com/public_api/v1/issue/search"
    )
    assert (
        handle_fqdn("XXXX.test.paloaltonetworks.com")
        == "https://api-XXXX.test.paloaltonetworks.com/public_api/v1/issue/search"
    )
    assert (
        handle_fqdn("https://XXXX.test.paloaltonetworks.com/public_api/v1/issue/search")
        == "https://XXXX.test.paloaltonetworks.com/public_api/v1/issue/search"
    )


@freeze_time("2024-01-23 10:00:00")
def test_getting_data_2(trigger, issue_response_2, issue_query_2):
    fqdn = trigger.module.configuration.fqdn
    issue_url = f"https://api-{fqdn}/public_api/v1/issue/search"

    with requests_mock.Mocker() as mock:
        mock.post(
            issue_url,
            status_code=200,
            json=issue_response_2,
            additional_matcher=lambda request: request.json() == issue_query_2,
        )

        trigger.get_all_issues(2)
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        issues = [orjson.loads(data) for data in calls[0]]
        assert len(issues) == 2
        assert all(issue.get("is_excluded") is False for issue in issues)


@freeze_time("2024-01-23 10:00:00")
def test_getting_data_3(trigger, issue_response_3_2, issue_response_3_1, issue_query_2, issue_query_4):
    fqdn = trigger.module.configuration.fqdn
    issue_url = f"https://api-{fqdn}/public_api/v1/issue/search"

    with requests_mock.Mocker() as mock:
        mock.post(
            issue_url,
            status_code=200,
            json=issue_response_3_2,
            additional_matcher=lambda request: request.json() == issue_query_2,
        )

        mock.post(
            issue_url,
            status_code=200,
            json=issue_response_3_1,
            additional_matcher=lambda request: request.json() == issue_query_4,
        )

        trigger.get_all_issues(2)
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        first_issues_batch = [orjson.loads(data) for data in calls[0]]
        second_issues_batch = [orjson.loads(data) for data in calls[1]]
        assert len(first_issues_batch) == 2
        assert len(second_issues_batch) == 1
        assert sorted(issue["issue_id"] for issue in first_issues_batch + second_issues_batch) == ["1", "2", "5930923"]


@freeze_time("2024-01-23 10:00:00")
def test_getting_data_0(trigger, issue_response_0, issue_query_2):
    fqdn = trigger.module.configuration.fqdn
    issue_url = f"https://api-{fqdn}/public_api/v1/issue/search"

    with requests_mock.Mocker() as mock:
        mock.post(
            issue_url,
            status_code=200,
            json=issue_response_0,
            additional_matcher=lambda request: request.json() == issue_query_2,
        )

        assert trigger.get_issues_by_offset(0, trigger.timestamp_cursor, 2) == (0, [])


@freeze_time("2024-01-23 10:00:00")
def test_getting_data_empty_issues(trigger, issue_response_empty, issue_query_2):
    fqdn = trigger.module.configuration.fqdn
    issue_url = f"https://api-{fqdn}/public_api/v1/issue/search"

    with requests_mock.Mocker() as mock:
        mock.post(
            issue_url,
            status_code=200,
            json=issue_response_empty,
            additional_matcher=lambda request: request.json() == issue_query_2,
        )

        assert trigger.get_issues_by_offset(0, trigger.timestamp_cursor, 2) == (0, [])


@freeze_time("2024-01-23 10:00:00")
def test_getting_data_400_http_code(trigger):
    fqdn = trigger.module.configuration.fqdn
    issue_url = f"https://api-{fqdn}/public_api/v1/issue/search"

    with patch("cortex_module.cortex_edr_connector.time"), requests_mock.Mocker() as mock:
        mock.post(issue_url, status_code=400)

        trigger.forward_next_batch()
        assert trigger.log_exception.called


@freeze_time("2024-01-23 10:00:00")
def test_getting_data_with_authentication_failure(trigger):
    fqdn = trigger.module.configuration.fqdn
    issue_url = f"https://api-{fqdn}/public_api/v1/issue/search"

    with patch("cortex_module.cortex_edr_connector.time"), requests_mock.Mocker() as mock:
        mock.post(issue_url, status_code=401)

        trigger.forward_next_batch()
        assert trigger.log.mock_calls == [
            call(level="critical", message="Authentication failed: Credentials are invalid")
        ]


@freeze_time("2024-01-23 10:00:00")
def test_getting_data_with_permission_failure(trigger):
    fqdn = trigger.module.configuration.fqdn
    issue_url = f"https://api-{fqdn}/public_api/v1/issue/search"

    with patch("cortex_module.cortex_edr_connector.time"), requests_mock.Mocker() as mock:
        mock.post(issue_url, status_code=403)

        trigger.forward_next_batch()
        assert trigger.log.mock_calls == [
            call(level="critical", message="Permission denied: The operation isn't allowed for these credentials")
        ]


@freeze_time("2024-01-23 10:00:00")
def test_getting_data_with_connection_failure(trigger):
    with (
        patch("cortex_module.cortex_edr_connector.time"),
        patch.object(
            trigger,
            "get_all_issues",
            side_effect=RequestsConnectionError("Remote end closed connection without response"),
        ),
    ):
        trigger.forward_next_batch()

        trigger.log.assert_any_call(
            level="warning",
            message="Temporary connection issue while fetching Cortex issues, will retry on next run",
        )


@freeze_time("2024-01-23 10:00:00")
def test_getting_data_reconnect_notification(trigger):
    with (
        patch("cortex_module.cortex_edr_connector.time"),
        patch.object(
            trigger,
            "get_all_issues",
            side_effect=[RequestsConnectionError("Remote end closed connection without response"), None],
        ),
    ):
        trigger.forward_next_batch()
        trigger.forward_next_batch()

        trigger.log.assert_any_call(
            level="warning",
            message="Temporary connection issue while fetching Cortex issues, will retry on next run",
        )
        trigger.log.assert_any_call(
            level="info", message="Cortex connection restored, the connector reconnected successfully"
        )


def test_normalize_issues_with_cache(trigger, issue_response_2):
    issues = issue_response_2["reply"]["issues"] * 10

    normalized_issues = trigger.normalize_issues(issues=issues)

    # caching should protect from duplicates
    assert len(normalized_issues) == 2


def test_normalize_issues_forward_updated_revision(trigger):
    issues = [
        {"issue_id": "123", "severity": "LOW", "modification_time": 1705912800000, "is_excluded": False},
        {"issue_id": "123", "severity": "LOW", "modification_time": 1705912800500, "is_excluded": True},
    ]

    normalized_issues = trigger.normalize_issues(issues=issues)
    decoded_issues = [orjson.loads(issue) for issue in normalized_issues]

    assert len(normalized_issues) == 2
    assert [issue["modification_time"] for issue in decoded_issues] == [1705912800000, 1705912800500]


def test_normalize_issues_without_issue_id(trigger):
    issues = [
        {"severity": "MEDIUM", "modification_time": 1705912900118, "is_excluded": False},
        {"issue_id": "123", "severity": "LOW", "modification_time": 1705912800000, "is_excluded": False},
    ]

    normalized_issues = trigger.normalize_issues(issues=issues)

    assert len(normalized_issues) == 1
    trigger.log.assert_called_with(level="warning", message="Skipping Cortex issue without issue_id")


@freeze_time("2024-01-23 10:00:00")
def test_timestamp_cursor_setter_keeps_exact_milliseconds(trigger):
    exact_timestamp = 1705912800500

    trigger.timestamp_cursor = exact_timestamp

    assert trigger._timestamp_cursor == exact_timestamp
    with trigger.context as cache:
        assert cache["timestamp_cursor"] == exact_timestamp


@freeze_time("2024-01-23 10:00:00")
def test_get_all_issues_no_data_logs_info(trigger):
    with patch.object(trigger, "get_issues_by_offset", return_value=(0, [])):
        trigger.get_all_issues(2)

    trigger.log.assert_any_call(message=f"No issues to forward at {trigger.timestamp_cursor}", level="info")
    trigger.push_events_to_intakes.assert_not_called()


@freeze_time("2024-01-23 10:00:00")
def test_get_all_issues_raises_when_modification_time_missing(trigger):
    issue_payload_without_modification_time = orjson.dumps({"issue_id": "1", "severity": "LOW"}).decode("utf-8")

    with patch.object(trigger, "get_issues_by_offset", return_value=(1, [issue_payload_without_modification_time])):
        with pytest.raises(ValueError, match="Received Cortex issue without modification_time"):
            trigger.get_all_issues(2)


@freeze_time("2024-01-23 10:00:00")
def test_forward_next_batch_http_error_without_response(trigger):
    with (
        patch("cortex_module.cortex_edr_connector.time"),
        patch.object(trigger, "get_all_issues", side_effect=HTTPError("boom")),
    ):
        trigger.forward_next_batch()

    trigger.log_exception.assert_called_with(ANY, message="Response does not contain any valid data")
