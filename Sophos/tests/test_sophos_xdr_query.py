import json
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
import requests_mock

from sophos_module.base import SophosModule
from sophos_module.trigger_sophos_xdr_query import SophosXDRQueryTrigger
from sophos_module.trigger_sophos_xdr_query import SophosXDRIOCQuery


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
def queryRun_message():
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
def queryRunFailed_message():
    return {
        "error": "ValidationException",
        "correlationId": "3f2aa7bc-bbb1-4f93-8d56-acad5f6ad3dc",
        "requestId": "3dc153c6-03a4-45c9-abb0-8d4a7e41a96f",
        "createdAt": "2023-07-18T09:23:25.449Z",
        "code": 400,
        "message": "Invalid time range 'from' field: 2023-07-18T10:52:22Z - cannot be in the future.",
    }


@pytest.fixture
def queryStatus_message():
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
def queryResults_message():
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
def queryResults_message1():
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
def nextqueryResults_message():
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
    trigger, authorization_message, whoami_message, queryRun_message, queryStatus_message, queryResults_message
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

        mock.post(url, json=queryRun_message)
        mock.get(url_query_status, json=queryStatus_message)
        mock.get(url_results, json=queryResults_message)
        trigger.getting_results("7")
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls[0]) == 7
        assert trigger.cursor.offset.date() == datetime.now(timezone.utc).date()


def test_getting_failed_results(trigger, authorization_message, whoami_message, queryRunFailed_message):
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

        mock.post(url, json=queryRunFailed_message)
        assert trigger.post_query("query_ioc") == ("failed", None)


def test_getting_next_results(
    trigger,
    authorization_message,
    whoami_message,
    queryRun_message,
    queryStatus_message,
    queryResults_message1,
    nextqueryResults_message,
):
    host = "https://api-eu01.central.sophos.com"
    url = f"{host}/xdr-query/v1/queries/runs"
    url_query_status = f"{host}/xdr-query/v1/queries/runs/7d00cf17-a987-4d07-ac88-93d4df89fa73"
    url_results = (
        f"{host}/xdr-query/v1/queries/runs/7d00cf17-a987-4d07-ac88-93d4df89fa73/results?maxSize=1000&pageSize=7"
    )
    url_next_results = f"{host}/xdr-query/v1/queries/runs/7d00cf17-a987-4d07-ac88-93d4df89fa73/results?maxSize=1000&pageSize=7&pageFromKey=AAAABw=="

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

        mock.post(url, json=queryRun_message)
        mock.get(url_query_status, json=queryStatus_message)
        mock.get(url_results, json=queryResults_message1)
        mock.get(url_next_results, json=nextqueryResults_message)
        trigger.getting_results("7")
        assert trigger.events_sum == 8
        assert trigger.cursor.offset.date() == datetime.now(timezone.utc).date()
        assert trigger.query["from"] == trigger.from_date.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_getting_results_with_compatibility_fallback_query(
    trigger, authorization_message, whoami_message, queryRun_message, queryStatus_message, queryResults_message
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

        mock.post(
            url,
            [
                {
                    "status_code": 400,
                    "json": {
                        "error": "ValidationException",
                        "message": "column ioc_detection_weight does not exist",
                    },
                },
                {"status_code": 200, "json": queryRun_message},
            ],
        )
        mock.get(url_query_status, json=queryStatus_message)
        mock.get(url_results, json=queryResults_message)

        trigger.getting_results("7")

        query_calls = [call for call in mock.request_history if call.method == "POST" and call.url == url]

        first_query = json.loads(query_calls[0].body.decode("utf-8"))
        second_query = json.loads(query_calls[1].body.decode("utf-8"))

        assert len(query_calls) == 2
        assert first_query["adHocQuery"]["template"] == "SELECT * FROM xdr_ioc_view WHERE ioc_detection_weight > 3"
        assert second_query["adHocQuery"]["template"] == "SELECT * FROM xdr_ioc_view WHERE ioc_severity > 3"
        assert trigger.push_events_to_intakes.call_count == 1


def test_getting_results_does_not_fallback_on_non_compatibility_error(trigger, authorization_message, whoami_message):
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

        mock.post(
            url,
            status_code=429,
            json={"error": "TooManyRequests", "message": "rate limit exceeded"},
        )

        trigger.getting_results("7")

        query_calls = [call for call in mock.request_history if call.method == "POST" and call.url == url]
        assert len(query_calls) == 1
        assert trigger.push_events_to_intakes.call_count == 0


def test_post_query_http_error_with_non_json_response_sets_last_error(trigger):
    response = Mock()
    response.status_code = 400
    response.text = "bad request"
    response.json.side_effect = ValueError("invalid json")

    trigger.client.run_query = Mock(return_value=response)

    result, query_id = trigger.post_query({"adHocQuery": {"template": "SELECT 1"}})

    assert (result, query_id) == ("failed", None)
    assert trigger._last_query_error == {"status_code": 400, "message": "bad request"}


def test_post_query_missing_query_id_sets_last_error(trigger):
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"status": "pending"}

    trigger.client.run_query = Mock(return_value=response)

    result, query_id = trigger.post_query({"adHocQuery": {"template": "SELECT 1"}})

    assert (result, query_id) == ("failed", None)
    assert trigger._last_query_error == {
        "status_code": 200,
        "message": "Missing query id in response",
    }


def test_post_query_unsuccessful_query_result_sets_last_error(trigger, monkeypatch):
    response_run_query = Mock()
    response_run_query.status_code = 200
    response_run_query.json.return_value = {"id": "query-id"}

    response_query_status = Mock()
    response_query_status.status_code = 500
    response_query_status.text = "status endpoint error"
    response_query_status.json.return_value = {"status": "finished", "result": "failed"}

    trigger.client.run_query = Mock(return_value=response_run_query)
    trigger.client.get_query_status = Mock(return_value=response_query_status)
    monkeypatch.setattr("sophos_module.trigger_sophos_xdr_query.time.sleep", lambda _: None)

    result, query_id = trigger.post_query({"adHocQuery": {"template": "SELECT 1"}})

    assert (result, query_id) == ("failed", "query-id")
    assert trigger._last_query_error == {
        "status_code": 500,
        "message": "Query execution result: failed",
    }


def test_is_missing_ioc_detection_weight_error_is_false_without_last_error(trigger):
    trigger._last_query_error = None

    assert trigger._is_missing_ioc_detection_weight_error() is False


def test_run_compatible_query_does_not_retry_for_other_errors(trigger):
    def _mock_post_query(_query):
        trigger._last_query_error = {
            "status_code": 400,
            "message": "column some_other_field does not exist",
        }
        return "failed", "query-id"

    trigger.post_query = Mock(side_effect=_mock_post_query)

    result, query_id = trigger.run_compatible_query()

    assert (result, query_id) == ("failed", "query-id")
    assert trigger.post_query.call_count == 1


def test_observe_items_events_lag_with_calendar_time_camel_case(trigger):
    trigger._observe_items_events_lag(
        [
            {"calendarTime": "2023-07-03T11:28:45.000Z"},
            {"calendarTime": "2023-07-03T11:22:45.000Z"},
        ]
    )


def test_run_compatible_query_failed_after_all_templates(trigger):
    def _mock_post_query(_query):
        trigger._last_query_error = {
            "status_code": 400,
            "message": "column ioc_detection_weight does not exist",
        }
        return "failed", None

    trigger.post_query = Mock(side_effect=_mock_post_query)

    result, query_id = trigger.run_compatible_query()

    assert (result, query_id) == ("failed", None)
    assert trigger.post_query.call_count == len(trigger.queries)
    assert trigger.log.call_count >= 1


def test_extract_event_timestamp_handles_invalid_values(trigger):
    assert trigger._extract_event_timestamp({"createdAt": None}) is None
    assert trigger._extract_event_timestamp({"createdAt": 123}) is None
    assert trigger._extract_event_timestamp({"createdAt": ""}) is None
    assert trigger._extract_event_timestamp({"createdAt": "not-a-date"}) is None


def test_extract_event_timestamp_falls_back_to_created_at(trigger):
    item = {"createdAt": "2023-07-03T11:28:45.000Z"}

    assert trigger._extract_event_timestamp(item) is not None


def test_base_queries_property_default_behavior(trigger):
    base_queries = SophosXDRQueryTrigger.queries.fget(trigger)

    assert base_queries == [trigger.query]
