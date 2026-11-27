import json
import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
import requests
import requests_mock

from sophos_module.base import SophosModule
from sophos_module.triggers.trigger_sophos_xdr_query import (
    FUSION_UPGRADE_MESSAGE,
    QUERY_STATUS_MIN_REQUEST_TIMEOUT,
    QUERY_STATUS_POLL_INTERVAL,
    QUERY_STATUS_TIMEOUT,
    SophosXDRIOCQuery,
    SophosXDRQueryTrigger,
)


@pytest.fixture
def trigger(symphony_storage):
    module = SophosModule()
    trigger = SophosXDRIOCQuery(module=module, data_path=symphony_storage)
    trigger.module.configuration = {
        "oauth2_authorization_url": "https://id.sophos.com/api/v2/oauth2/token",
        "api_host": "https://api.central.sophos.com",
        "client_id": "my-id",
        "client_secret": "my-password",
    }

    trigger.configuration = {
        "frequency": 604800,
        "tenant_id": "4feff6df-7454-4036-923d-7b2444462416",
        "chunk_size": 1,
        "intake_key": "0123456789",
    }

    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()
    return trigger


@pytest.fixture
def authorization_message():
    return {
        "access_token": "access_token",
        "refresh_token": "refresh_token",
        "token_type": "bearer",
        "message": "OK",
        "errorCode": "success",
        "expires_in": 3600,
    }


@pytest.fixture
def whoami_message():
    host = "https://api-eu01.central.sophos.com"
    return {
        "id": "ea106f70-96b1-4851-bd31-e4395ea407d2",
        "idType": "tenant",
        "apiHosts": {
            "global": "https://api.central.sophos.com",
            "dataRegion": host,
        },
    }


@pytest.fixture
def query_run_message():
    return {
        "id": "7d00cf17-a987-4d07-ac88-93d4df89fa73",
        "createdAt": "2023-06-30T08:14:55.628Z",
        "createdBy": {
            "id": "ec3e58df-3b9a-4970-aedc-f9b756f0fd6d",
            "type": "service",
            "accountId": "4feff6df-7454-4036-923d-7b2444462416",
            "accountType": "tenant",
        },
        "expiresAt": "2023-06-30T10:14:55.649Z",
        "result": "notAvailable",
        "status": "pending",
        "template": "SELECT * FROM xdr_ioc_view",
        "from": "2023-06-29T08:14:55.625Z",
        "to": "2023-06-30T08:14:55.625Z",
    }


@pytest.fixture
def query_run_failed_message():
    return {
        "error": "ValidationException",
        "correlationId": "3f2aa7bc-bbb1-4f93-8d56-acad5f6ad3dc",
        "requestId": "3dc153c6-03a4-45c9-abb0-8d4a7e41a96f",
        "createdAt": "2023-07-18T09:23:25.449Z",
        "code": 400,
        "message": "Invalid time range 'from' field: 2023-07-18T10:52:22Z - cannot be in the future.",
    }


@pytest.fixture
def query_status_message():
    return {
        "id": "7d00cf17-a987-4d07-ac88-93d4df89fa73",
        "createdAt": "2023-06-30T08:14:55.628Z",
        "createdBy": {
            "id": "ec3e58df-3b9a-4970-aedc-f9b756f0fd6d",
            "type": "service",
            "accountId": "4feff6df-7454-4036-923d-7b2444462416",
            "accountType": "tenant",
        },
        "expiresAt": "2023-06-30T10:14:56.084Z",
        "finishedAt": "2023-06-30T08:15:01.252Z",
        "result": "succeeded",
        "status": "finished",
        "template": "SELECT * FROM xdr_ioc_view",
        "from": "2023-06-29T08:14:55.625Z",
        "to": "2023-06-30T08:14:55.625Z",
    }


@pytest.fixture
def query_results_message():
    return {
        "items": [
            {
                "upload_size": 1033,
                "record_identifier": "22648a5236e08f6e7a930f46d1680a9ea11365fed49ae4eb3a6b18366acf8c1c",
                "ioc_severity": 4,
                "calendar_time": "2023-07-03T11:28:45.000Z",
            },
            {
                "upload_size": 1296,
                "record_identifier": "ca930c75bfa5992d669463fdd211e9ccf85f1ff6876466704526656e94b84410",
                "ioc_severity": 3,
                "calendar_time": "2023-07-03T11:22:45.000Z",
            },
            {
                "upload_size": 1021,
                "record_identifier": "9ed3ca2f862b037abbab3f0d4ba56a8534b4fb37f5ffae1bedcf007c0595a2aa",
                "ioc_severity": 4,
                "calendar_time": "2023-07-03T11:19:45.000Z",
            },
            {
                "upload_size": 1254,
                "record_identifier": "e96c524f39ee22d8c42333b853a05993f1998634385a8f6a8c9f1bf8db7d6177",
                "ioc_severity": 3,
                "calendar_time": "2023-07-03T10:11:45.000Z",
            },
            {
                "upload_size": 983,
                "record_identifier": "e74f7be8a322b451df13c94a007f22a61a2f7d82236f7ad0fd842632ce31e6b0",
                "ioc_severity": 5,
                "calendar_time": "2023-07-03T10:09:45.000Z",
            },
            {
                "upload_size": 1296,
                "record_identifier": "9f64e276598a3b57b98a4185abc1c4a3db9e05725d985a28709c8cd350cf5b9f",
                "ioc_severity": 3,
                "calendar_time": "2023-07-03T09:09:45.000Z",
            },
            {
                "upload_size": 1744,
                "record_identifier": "9a59a621cdb463fecd27f734f4b12f912dd16a708d28d6b6119162e1f37aba61",
                "ioc_severity": 5,
                "calendar_time": "2023-07-03T09:08:45.000Z",
            },
        ],
        "metadata": {
            "columns": [
                {"name": "customer_id", "type": "string"},
                {"name": "endpoint_id", "type": "string"},
                {"name": "ingestion_timestamp", "type": "timestamp"},
                {"name": "schema_version", "type": "string"},
            ]
        },
        "pages": {"size": 7, "maxSize": 2000, "total": 1, "items": 7},
    }


@pytest.fixture
def query_results_message1():
    return {
        "items": [
            {
                "upload_size": 1033,
                "record_identifier": "22648a5236e08f6e7a930f46d1680a9ea11365fed49ae4eb3a6b18366acf8c1c",
                "ioc_severity": 4,
            },
            {
                "upload_size": 1296,
                "record_identifier": "ca930c75bfa5992d669463fdd211e9ccf85f1ff6876466704526656e94b84410",
                "ioc_severity": 3,
            },
            {
                "upload_size": 1021,
                "record_identifier": "9ed3ca2f862b037abbab3f0d4ba56a8534b4fb37f5ffae1bedcf007c0595a2aa",
                "ioc_severity": 4,
            },
            {
                "upload_size": 1254,
                "record_identifier": "e96c524f39ee22d8c42333b853a05993f1998634385a8f6a8c9f1bf8db7d6177",
                "ioc_severity": 3,
            },
            {
                "upload_size": 983,
                "record_identifier": "e74f7be8a322b451df13c94a007f22a61a2f7d82236f7ad0fd842632ce31e6b0",
                "ioc_severity": 5,
            },
            {
                "upload_size": 1296,
                "record_identifier": "9f64e276598a3b57b98a4185abc1c4a3db9e05725d985a28709c8cd350cf5b9f",
                "ioc_severity": 3,
            },
            {
                "upload_size": 1744,
                "record_identifier": "9a59a621cdb463fecd27f734f4b12f912dd16a708d28d6b6119162e1f37aba61",
                "ioc_severity": 5,
            },
        ],
        "metadata": {
            "columns": [
                {"name": "customer_id", "type": "string"},
                {"name": "endpoint_id", "type": "string"},
                {"name": "ingestion_timestamp", "type": "timestamp"},
                {"name": "schema_version", "type": "string"},
            ]
        },
        "pages": {"nextKey": "AAAABw==", "size": 7, "maxSize": 2000, "total": 2, "items": 8},
    }


@pytest.fixture
def next_query_results_message():
    return {
        "items": [
            {
                "upload_size": 1033,
                "record_identifier": "22648a5236e08f6e7a930f46d1680a9ea11365fed49ae4eb3a6b18366acf8c1c",
                "ioc_severity": 4,
            }
        ],
        "metadata": {
            "columns": [
                {"name": "customer_id", "type": "string"},
                {"name": "endpoint_id", "type": "string"},
                {"name": "ingestion_timestamp", "type": "timestamp"},
                {"name": "schema_version", "type": "string"},
            ]
        },
        "pages": {"fromKey": "AAAABw==", "size": 7, "maxSize": 2000, "total": 2, "items": 8},
    }


def test_getting_results(
    trigger, authorization_message, whoami_message, query_run_message, query_status_message, query_results_message
):
    host = "https://api-eu01.central.sophos.com"
    url = f"{host}/xdr-query/v1/queries/runs"
    url_query_status = f"{host}/xdr-query/v1/queries/runs/7d00cf17-a987-4d07-ac88-93d4df89fa73"
    url_results = (
        f"{host}/xdr-query/v1/queries/runs/7d00cf17-a987-4d07-ac88-93d4df89fa73/results?maxSize=1000&pageSize=7"
    )

    with requests_mock.Mocker() as mock:
        mock.post(
            f"{trigger.module.configuration.oauth2_authorization_url}",
            status_code=200,
            json=authorization_message,
        )

        mock.get(
            f"{trigger.module.configuration.api_host}/whoami/v1",
            status_code=200,
            json=whoami_message,
        )

        mock.post(url, json=query_run_message)
        mock.get(url_query_status, json=query_status_message)
        mock.get(url_results, json=query_results_message)
        trigger.getting_results("7")
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls[0]) == 7
        assert trigger.cursor.offset.date() == datetime.now(UTC).date()


def test_getting_failed_results(trigger, authorization_message, whoami_message, query_run_failed_message):
    host = "https://api-eu01.central.sophos.com"
    url = f"{host}/xdr-query/v1/queries/runs"

    with requests_mock.Mocker() as mock:
        mock.post(
            f"{trigger.module.configuration.oauth2_authorization_url}",
            status_code=200,
            json=authorization_message,
        )

        mock.get(
            f"{trigger.module.configuration.api_host}/whoami/v1",
            status_code=200,
            json=whoami_message,
        )

        mock.post(url, json=query_run_failed_message)
        assert trigger.post_query("query_ioc") == ("failed", None)


def test_getting_next_results(
    trigger,
    authorization_message,
    whoami_message,
    query_run_message,
    query_status_message,
    query_results_message1,
    next_query_results_message,
):
    host = "https://api-eu01.central.sophos.com"
    url = f"{host}/xdr-query/v1/queries/runs"
    url_query_status = f"{host}/xdr-query/v1/queries/runs/7d00cf17-a987-4d07-ac88-93d4df89fa73"
    url_results = (
        f"{host}/xdr-query/v1/queries/runs/7d00cf17-a987-4d07-ac88-93d4df89fa73/results?maxSize=1000&pageSize=7"
    )
    url_next_results = (
        f"{host}/xdr-query/v1/queries/runs/7d00cf17-a987-4d07-ac88-93d4df89fa73/results"
        "?maxSize=1000&pageSize=7&pageFromKey=AAAABw=="
    )

    with requests_mock.Mocker() as mock:
        mock.post(
            f"{trigger.module.configuration.oauth2_authorization_url}",
            status_code=200,
            json=authorization_message,
        )

        mock.get(
            f"{trigger.module.configuration.api_host}/whoami/v1",
            status_code=200,
            json=whoami_message,
        )

        mock.post(url, json=query_run_message)
        mock.get(url_query_status, json=query_status_message)
        mock.get(url_results, json=query_results_message1)
        mock.get(url_next_results, json=next_query_results_message)
        trigger.getting_results("7")
        assert trigger.events_sum == 8
        assert trigger.cursor.offset.date() == datetime.now(UTC).date()
        assert trigger.query["from"] == trigger.from_date.strftime("%Y-%m-%dT%H:%M:%SZ")


def _mock_authentication(mock, trigger, authorization_message, whoami_message):
    mock.post(trigger.module.configuration.oauth2_authorization_url, status_code=200, json=authorization_message)
    mock.get(f"{trigger.module.configuration.api_host}/whoami/v1", status_code=200, json=whoami_message)


def test_post_query_forbidden_logs_role_hint(trigger, authorization_message, whoami_message):
    url = "https://api-eu01.central.sophos.com/xdr-query/v1/queries/runs"
    with requests_mock.Mocker() as mock:
        _mock_authentication(mock, trigger, authorization_message, whoami_message)
        mock.post(url, status_code=403, json={"error": "UNAUTHORIZED_ACCESS", "message": "Forbidden"})

        assert trigger.post_query(trigger.query) == ("failed", None)

    assert [call.kwargs["message"] for call in trigger.log.call_args_list] == [
        "Failed to post the query to the Sophos data lake: status 403 - UNAUTHORIZED_ACCESS: Forbidden"
        ". Check that the API credential has the 'Service Principal Forensics' role"
        " and that the XDR licence of the tenant is valid"
    ]


def test_post_query_without_query_id(trigger, authorization_message, whoami_message):
    url = "https://api-eu01.central.sophos.com/xdr-query/v1/queries/runs"
    with requests_mock.Mocker() as mock:
        _mock_authentication(mock, trigger, authorization_message, whoami_message)
        mock.post(url, status_code=201, json={"status": "pending"})

        assert trigger.post_query(trigger.query) == ("failed", None)

    assert any(call.kwargs.get("level") == "error" for call in trigger.log.call_args_list)


def test_post_query_execution_failed_logs_details(
    trigger, authorization_message, whoami_message, query_run_message, query_status_message
):
    host = "https://api-eu01.central.sophos.com"
    query_id = query_run_message["id"]
    failed_status = {**query_status_message, "result": "failed", "error": {"code": "QUERY_FAILED"}}

    with requests_mock.Mocker() as mock:
        _mock_authentication(mock, trigger, authorization_message, whoami_message)
        mock.post(f"{host}/xdr-query/v1/queries/runs", json=query_run_message)
        mock.get(f"{host}/xdr-query/v1/queries/runs/{query_id}", json=failed_status)

        assert trigger.post_query(trigger.query) == ("failed", query_id)

    messages = [call.kwargs["message"] for call in trigger.log.call_args_list if call.kwargs.get("level") == "error"]
    assert any("QUERY_FAILED" in message for message in messages)


def test_observe_items_events_lag_without_fractional_seconds(trigger, monkeypatch):
    lag = Mock()
    monkeypatch.setattr("sophos_module.triggers.trigger_sophos_xdr_query.EVENTS_LAG", lag)
    trigger._observe_items_events_lag([{"calendar_time": "2023-07-03T11:28:45Z"}])
    lag.labels.return_value.set.assert_called_once()

    lag.reset_mock()
    trigger._observe_items_events_lag([{"foo": "bar"}])
    lag.labels.return_value.set.assert_not_called()


def _mock_tenant_markers(mock, trigger, authorization_message, whoami_message, **kwargs):
    _mock_authentication(mock, trigger, authorization_message, whoami_message)
    mock.post("https://api.taegis.sophos.com/graphql", **kwargs)


@pytest.mark.parametrize(
    "markers, expected",
    [
        pytest.param({"xdrOwnership": "securityOperations", "hydrateTo": "taegis"}, True, id="fusion"),
        pytest.param({"xdrOwnership": "securityOperations", "hydrateTo": None}, True, id="sec-ops"),
        pytest.param({"xdrOwnership": "central", "hydrateTo": "taegis"}, True, id="taegis"),
        pytest.param({"xdrOwnership": "central", "hydrateTo": None}, False, id="legacy"),
        pytest.param(None, False, id="no-central-tenant"),
    ],
)
def test_check_fusion_upgrade(trigger, authorization_message, whoami_message, caplog, markers, expected):
    caplog.set_level(logging.INFO)
    with requests_mock.Mocker() as mock:
        _mock_tenant_markers(
            mock,
            trigger,
            authorization_message,
            whoami_message,
            json={"data": {"tenant": {"id": "427579", "centralTenant": markers}}},
        )
        assert trigger.check_fusion_upgrade() is expected
        assert mock.last_request.json()["variables"] == {"id": whoami_message["id"]}

    assert trigger.fusion_upgraded is expected
    # the user only sees the upgrade error; the raw markers go to the pod logs
    assert [call.kwargs["message"] for call in trigger.log.call_args_list] == (
        [FUSION_UPGRADE_MESSAGE] if expected else []
    )
    pod_logs = [record.getMessage() for record in caplog.records if "Sophos Fusion markers" in record.getMessage()]
    assert len(pod_logs) == 1
    if markers:
        assert f"xdrOwnership={markers['xdrOwnership']}" in pod_logs[0]


@pytest.mark.parametrize(
    "response",
    [
        pytest.param({"status_code": 403, "json": {"message": "Forbidden"}}, id="http-error"),
        pytest.param(
            {"json": {"data": None, "errors": [{"message": "not found", "extensions": {"code": "NOT_FOUND"}}]}},
            id="graphql-error",
        ),
        pytest.param({"json": {"data": {"tenant": None}}}, id="no-tenant"),
    ],
)
def test_check_fusion_upgrade_failure_is_ignored(trigger, authorization_message, whoami_message, response):
    with requests_mock.Mocker() as mock:
        _mock_tenant_markers(mock, trigger, authorization_message, whoami_message, **response)
        assert trigger.check_fusion_upgrade() is None
        assert trigger.fusion_upgraded is None

    # best effort: nothing shown to the user
    trigger.log.assert_not_called()


def test_warn_if_stalled_when_markers_unknown(trigger):
    trigger.from_date = datetime.now(UTC) - timedelta(days=31)

    trigger.warn_if_stalled()
    trigger.warn_if_stalled()

    warnings = [call for call in trigger.log.call_args_list if call.kwargs.get("level") == "warning"]
    assert len(warnings) == 1
    assert "Sophos Fusion" in warnings[0].kwargs["message"]


@pytest.mark.parametrize("upgraded", [True, False])
def test_warn_if_stalled_silent_when_markers_answered(trigger, upgraded):
    trigger.fusion_upgraded = upgraded
    trigger.from_date = datetime.now(UTC) - timedelta(days=31)

    trigger.warn_if_stalled()

    trigger.log.assert_not_called()


def test_warn_if_stalled_recent_checkpoint(trigger):
    trigger.from_date = datetime.now(UTC) - timedelta(days=2)

    trigger.warn_if_stalled()

    trigger.log.assert_not_called()


def test_check_fusion_upgrade_daily(trigger):
    trigger.check_fusion_upgrade = Mock()

    trigger.check_fusion_upgrade_daily()
    trigger._last_fusion_check = datetime.now(UTC)
    trigger.check_fusion_upgrade_daily()
    trigger._last_fusion_check = datetime.now(UTC) - timedelta(days=1, minutes=1)
    trigger.check_fusion_upgrade_daily()

    assert trigger.check_fusion_upgrade.call_count == 2


@pytest.mark.parametrize(
    "age, expected_age",
    [
        pytest.param(timedelta(days=2), timedelta(days=2), id="recent"),
        pytest.param(timedelta(days=45), timedelta(days=30), id="capped-to-30-days"),
    ],
)
def test_from_date_is_capped(trigger, age, expected_age):
    trigger.from_date = datetime.now(UTC) - age

    assert abs((datetime.now(UTC) - trigger.from_date) - expected_age) < timedelta(seconds=5)


def test_base_query_is_abstract(trigger):
    with pytest.raises(NotImplementedError):
        SophosXDRQueryTrigger.query.fget(trigger)


@pytest.mark.parametrize("chunk_size, expected", [(1, 1000), (1000, 1000), (5000, 5000)])
def test_pagination_limit(trigger, chunk_size, expected):
    trigger.configuration.chunk_size = chunk_size
    assert trigger.pagination_limit == expected


def test_getting_results_query_failed(trigger):
    trigger.post_query = Mock(return_value=("failed", None))
    trigger.warn_if_stalled = Mock()

    trigger.getting_results(1000)

    trigger.push_events_to_intakes.assert_not_called()
    trigger.warn_if_stalled.assert_not_called()
    # the cause is logged by post_query: nothing more for the user
    trigger.log.assert_not_called()


def test_getting_results_without_items(trigger, authorization_message, whoami_message):
    trigger.post_query = Mock(return_value=("succeeded", "query-id"))
    trigger.warn_if_stalled = Mock()
    checkpoint = trigger.cursor.offset

    with requests_mock.Mocker() as mock:
        _mock_authentication(mock, trigger, authorization_message, whoami_message)
        mock.get(
            "https://api-eu01.central.sophos.com/xdr-query/v1/queries/runs/query-id/results",
            json={"items": [], "pages": {}},
        )
        trigger.getting_results(1000)

    trigger.push_events_to_intakes.assert_not_called()
    trigger.warn_if_stalled.assert_called_once()
    assert trigger.cursor.offset == checkpoint


def test_access_refused_is_shown_once_per_hour(trigger, authorization_message, whoami_message):
    """A 403 lasts until the customer fixes the credential: shown once per hour, not once per cycle."""
    url = "https://api-eu01.central.sophos.com/xdr-query/v1/queries/runs"
    with requests_mock.Mocker() as mock:
        _mock_authentication(mock, trigger, authorization_message, whoami_message)
        mock.post(
            url,
            [
                {
                    "status_code": 403,
                    "json": {"error": "UNAUTHORIZED_ACCESS", "message": "Forbidden", "requestId": "1"},
                },
                {
                    "status_code": 403,
                    "json": {"error": "UNAUTHORIZED_ACCESS", "message": "Forbidden", "requestId": "2"},
                },
            ],
        )
        trigger.post_query(trigger.query)
        trigger.post_query(trigger.query)

    assert [call.kwargs["message"] for call in trigger.log.call_args_list] == [
        "Failed to post the query to the Sophos data lake: status 403 - UNAUTHORIZED_ACCESS: Forbidden"
        ". Check that the API credential has the 'Service Principal Forensics' role"
        " and that the XDR licence of the tenant is valid"
    ]


def test_getting_results_logs_a_summary_in_the_pod_logs_only(
    trigger, authorization_message, whoami_message, query_results_message, caplog
):
    caplog.set_level(logging.INFO)
    trigger.post_query = Mock(return_value=("succeeded", "query-id"))

    with requests_mock.Mocker() as mock:
        _mock_authentication(mock, trigger, authorization_message, whoami_message)
        mock.get(
            "https://api-eu01.central.sophos.com/xdr-query/v1/queries/runs/query-id/results",
            json={**query_results_message, "pages": {}},
        )
        trigger.getting_results(1000)

    trigger.log.assert_not_called()
    summary = [record.getMessage() for record in caplog.records if "IoCs collected" in record.getMessage()]
    assert len(summary) == 1 and "pages=1" in summary[0] and "forwarded=7" in summary[0]


def test_check_fusion_upgrade_is_a_single_short_attempt(trigger):
    trigger.authentication = Mock()
    trigger.client.graphql = Mock(side_effect=requests.ConnectTimeout())

    assert trigger.check_fusion_upgrade() is None

    trigger.client.graphql.assert_called_once()
    assert trigger.client.graphql.call_args.kwargs == {"best_effort": True}
    trigger.log.assert_not_called()


def test_collect_and_daily_fusion_check(trigger):
    trigger.getting_results = Mock()
    trigger.check_fusion_upgrade_daily = Mock()

    trigger.before_collect()
    trigger.collect()

    trigger.check_fusion_upgrade_daily.assert_called_once_with()
    trigger.getting_results.assert_called_once_with(trigger.pagination_limit)
    assert trigger.name == "Sophos IoC query trigger"


STATUS_URL = "https://api-eu01.central.sophos.com/xdr-query/v1/queries/runs/7d00cf17-a987-4d07-ac88-93d4df89fa73"


@pytest.fixture
def mock_query(trigger, authorization_message, whoami_message, query_run_message):
    with requests_mock.Mocker() as mock:
        _mock_authentication(mock, trigger, authorization_message, whoami_message)
        mock.post("https://api-eu01.central.sophos.com/xdr-query/v1/queries/runs", json=query_run_message)
        yield mock


@pytest.mark.parametrize(
    "transient_status",
    [pytest.param(429, id="rate-limited"), pytest.param(503, id="server-error")],
)
def test_query_status_transient_errors_are_polled_again(
    trigger, mock_query, query_status_message, no_sleep, transient_status
):
    # the urllib3 adapter retries 429 and 5xx itself: disable it to see the trigger behaviour
    trigger.client.get_query_status = Mock(
        side_effect=[
            _response(transient_status, {"message": "busy"}, STATUS_URL),
            _response(200, {**query_status_message, "status": "pending"}, STATUS_URL),
            _response(200, query_status_message, STATUS_URL),
        ]
    )

    assert trigger.post_query(trigger.query) == ("succeeded", query_status_message["id"])

    assert no_sleep == [2, 2, 2]
    assert len(trigger.log.call_args_list) == 1


@pytest.mark.parametrize("client_status", [400, 403, 404])
def test_query_status_client_errors_stop_the_polling(trigger, mock_query, no_sleep, client_status):
    trigger.client.get_query_status = Mock(return_value=_response(client_status, {"message": "gone"}, STATUS_URL))

    assert trigger.post_query(trigger.query) == ("failed", "7d00cf17-a987-4d07-ac88-93d4df89fa73")

    assert no_sleep == [2]
    assert (
        trigger.log.call_args_list[0]
        .kwargs["message"]
        .startswith(f"Failed to get the status of the Sophos data lake query: status {client_status} - None: gone")
    )


@pytest.fixture
def clock(monkeypatch, no_sleep):
    """Fake monotonic clock, moved forward by the sleeps and by the tests (slow requests)."""
    now = [1000.0]

    def sleep(seconds: float) -> None:
        no_sleep.append(seconds)
        now[0] += seconds

    monkeypatch.setattr("time.sleep", sleep)
    monkeypatch.setattr("time.monotonic", lambda: now[0])
    return now


def test_query_status_polling_is_capped(trigger, mock_query, query_status_message, no_sleep, clock):
    trigger.client.get_query_status = Mock(
        return_value=_response(200, {**query_status_message, "status": "pending"}, STATUS_URL)
    )

    assert trigger.post_query(trigger.query) == ("failed", "7d00cf17-a987-4d07-ac88-93d4df89fa73")

    expected_polls = QUERY_STATUS_TIMEOUT // QUERY_STATUS_POLL_INTERVAL
    assert trigger.client.get_query_status.call_count == expected_polls
    assert len(no_sleep) == expected_polls
    assert [call.kwargs["message"] for call in trigger.log.call_args_list] == [
        "The Sophos data lake query did not finish within 5 minutes: retried on the next cycle"
    ]


def test_query_status_polling_deadline_includes_slow_requests(trigger, mock_query, query_status_message, clock):
    """The deadline bounds the elapsed time, not the number of polls; each request gets the remaining time."""
    timeouts: list[float] = []

    def slow_status(query_id: str, timeout: float) -> requests.Response:
        timeouts.append(timeout)
        clock[0] += 250
        return _response(200, {**query_status_message, "status": "pending"}, STATUS_URL)

    trigger.client.get_query_status = Mock(side_effect=slow_status)

    assert trigger.post_query(trigger.query) == ("failed", "7d00cf17-a987-4d07-ac88-93d4df89fa73")

    # 2 s sleep + 250 s request, twice: past the 300 s deadline; the second request gets the 46 s left
    assert trigger.client.get_query_status.call_count == 2
    assert timeouts == [60, QUERY_STATUS_TIMEOUT - 2 * QUERY_STATUS_POLL_INTERVAL - 250]


def test_query_status_request_timeout_has_a_floor(trigger, mock_query, query_status_message, clock):
    def status(query_id: str, timeout: float) -> requests.Response:
        clock[0] += QUERY_STATUS_TIMEOUT - QUERY_STATUS_POLL_INTERVAL - 1
        return _response(200, {**query_status_message, "status": "pending"}, STATUS_URL)

    trigger.client.get_query_status = Mock(side_effect=status)

    trigger.post_query(trigger.query)

    # second poll: 1 s left after the sleep, below the floor
    assert trigger.client.get_query_status.call_args_list[1].kwargs["timeout"] == QUERY_STATUS_MIN_REQUEST_TIMEOUT


def _response(status_code, body, url):
    response = requests.Response()
    response.status_code = status_code
    response.url = url
    response._content = json.dumps(body).encode()
    return response
