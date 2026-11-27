from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
import requests_mock

from sophos_module.base import SophosModule
from sophos_module.triggers.trigger_sophos_xdr_query import SophosXDRIOCQuery


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

    messages = [call.kwargs["message"] for call in trigger.log.call_args_list if call.kwargs.get("level") == "error"]
    assert any("403" in message and "Service Principal Forensics" in message for message in messages)


def test_post_query_without_query_id(trigger, authorization_message, whoami_message):
    url = "https://api-eu01.central.sophos.com/xdr-query/v1/queries/runs"
    with requests_mock.Mocker() as mock:
        _mock_authentication(mock, trigger, authorization_message, whoami_message)
        mock.post(url, status_code=201, json={"status": "pending"})

        assert trigger.post_query(trigger.query) == ("failed", None)

    assert any(call.kwargs.get("level") == "error" for call in trigger.log.call_args_list)


def test_post_query_execution_failed_logs_details(
    trigger, authorization_message, whoami_message, query_run_message, query_status_message, monkeypatch
):
    host = "https://api-eu01.central.sophos.com"
    query_id = query_run_message["id"]
    failed_status = {**query_status_message, "result": "failed", "error": {"code": "QUERY_FAILED"}}
    monkeypatch.setattr("sophos_module.triggers.trigger_sophos_xdr_query.time.sleep", lambda _: None)

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


def test_check_fusion_upgrade_on_upgraded_tenant(trigger, authorization_message, whoami_message):
    with requests_mock.Mocker() as mock:
        _mock_tenant_markers(
            mock,
            trigger,
            authorization_message,
            whoami_message,
            json={
                "data": {
                    "tenant": {
                        "id": "427579",
                        "centralTenant": {"xdrOwnership": "securityOperations", "hydrateTo": "taegis"},
                    }
                }
            },
        )
        assert trigger.check_fusion_upgrade() is True
        assert mock.last_request.json()["variables"] == {"id": whoami_message["id"]}

    levels = [call.kwargs["level"] for call in trigger.log.call_args_list]
    assert "error" in levels


def test_check_fusion_upgrade_on_legacy_tenant(trigger, authorization_message, whoami_message):
    with requests_mock.Mocker() as mock:
        _mock_tenant_markers(
            mock,
            trigger,
            authorization_message,
            whoami_message,
            json={"data": {"tenant": {"id": "1", "centralTenant": {"xdrOwnership": "central", "hydrateTo": None}}}},
        )
        assert trigger.check_fusion_upgrade() is False

    assert all(call.kwargs["level"] == "info" for call in trigger.log.call_args_list)


@pytest.mark.parametrize(
    "response",
    [
        {"status_code": 403, "json": {"message": "Forbidden"}},
        {"json": {"data": None, "errors": [{"message": "not found", "extensions": {"code": "NOT_FOUND"}}]}},
    ],
)
def test_check_fusion_upgrade_failure_is_ignored(trigger, authorization_message, whoami_message, response):
    with requests_mock.Mocker() as mock:
        _mock_tenant_markers(mock, trigger, authorization_message, whoami_message, **response)
        assert trigger.check_fusion_upgrade() is None
        assert trigger.fusion_upgraded is None

    assert all(call.kwargs["level"] == "info" for call in trigger.log.call_args_list)


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
