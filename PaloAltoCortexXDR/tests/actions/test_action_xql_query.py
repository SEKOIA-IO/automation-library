from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, call, patch

import orjson
import pytest
import requests_mock
from freezegun import freeze_time
from requests.exceptions import HTTPError
from sekoia_automation.storage import PersistentJSON

from cortex_module.actions.action_comment_alert import CommentAlertAction, CommentAlertArguments
from cortex_module.actions.action_update_alert import Severity, Status, UpdateAlertAction, UpdateAlertArguments
from cortex_module.actions.action_xql_query import XQLQueryAction, XQLQueryArguments
from cortex_module.base import CortexModule
from cortex_module.cortex_edr_connector import CortexQueryEDRTrigger
from cortex_module.helper import handle_fqdn


@pytest.fixture
def action(module, symphony_storage):
    action = XQLQueryAction(module=module, data_path=symphony_storage)

    action.log_exception = Mock()
    action.log = Mock()

    return action


@pytest.fixture
def arguments_without_time() -> XQLQueryArguments:
    return XQLQueryArguments(
        query="SELECT * FROM test",
        tenants=["tenant1", "tenant2"],
        timeframe_from=1,
        timeframe_to=2,
        max_wait_time=0,
    )


@pytest.fixture
def arguments_with_time() -> XQLQueryArguments:
    return XQLQueryArguments(
        query="SELECT * FROM test",
        max_wait_time=11,
    )


def test_run_action_success(action, arguments_without_time):
    fqdn = action.module.configuration.fqdn
    url_start_query = f"https://api-{fqdn}/public_api/v1/xql/start_xql_query"
    url_result_query = f"https://api-{fqdn}/public_api/v1/xql/get_query_result"

    with requests_mock.Mocker() as mock:
        mock.post(
            url_start_query,
            status_code=200,
            json={"reply": "some-query-id"},
            additional_matcher=lambda request: request.json()
            == {
                "request_data": {
                    "query": arguments_without_time.query,
                    "tenants": arguments_without_time.tenants,
                    "timeframe": {
                        "from": arguments_without_time.timeframe_from,
                        "to": arguments_without_time.timeframe_to,
                    },
                }
            },
        )

        mock.post(
            url_result_query,
            status_code=200,
            json={
                "reply": {
                    "status": "success",
                    "results": {
                        "data": [
                            {"key1": "value1", "key2": "value2"},
                            {"key1": "value3", "key2": "value4"},
                        ],
                        "total_count": 2,
                    },
                }
            },
            additional_matcher=lambda request: request.json()
            == {
                "request_data": {
                    "query_id": "some-query-id",
                    "pending_flag": True,
                    "limit": 1000,
                    "format": "json",
                }
            },
        )

        assert action.run(arguments_without_time) == {
            "results": {
                "data": [
                    {"key1": "value1", "key2": "value2"},
                    {"key1": "value3", "key2": "value4"},
                ],
                "total_count": 2,
            }
        }


def test_run_action_success_1(action, arguments_with_time):
    fqdn = action.module.configuration.fqdn
    url_start_query = f"https://api-{fqdn}/public_api/v1/xql/start_xql_query"
    url_result_query = f"https://api-{fqdn}/public_api/v1/xql/get_query_result"

    with requests_mock.Mocker() as mock:
        mock.post(
            url_start_query,
            status_code=200,
            json={"reply": "some-query-id"},
            additional_matcher=lambda request: request.json()
            == {
                "request_data": {
                    "query": arguments_with_time.query,
                }
            },
        )

        mock.post(
            url_result_query,
            [
                {"status_code": 200, "json": {"reply": {"status": "pending"}}},
                {
                    "status_code": 200,
                    "json": {
                        "reply": {
                            "status": "success",
                            "results": {
                                "data": [
                                    {"key1": "value1", "key2": "value2"},
                                    {"key1": "value3", "key2": "value4"},
                                ],
                                "total_count": 2,
                            },
                        }
                    },
                },
            ],
        )

        assert action.run(arguments_with_time) == {
            "results": {
                "data": [
                    {"key1": "value1", "key2": "value2"},
                    {"key1": "value3", "key2": "value4"},
                ],
                "total_count": 2,
            }
        }


def test_run_action_fail_1(action, arguments_without_time):
    fqdn = action.module.configuration.fqdn
    url_start_query = f"https://api-{fqdn}/public_api/v1/xql/start_xql_query"
    url_result_query = f"https://api-{fqdn}/public_api/v1/xql/get_query_result"

    with requests_mock.Mocker() as mock:
        mock.post(
            url_start_query,
            status_code=200,
            json={"reply": "some-query-id"},
            additional_matcher=lambda request: request.json()
            == {
                "request_data": {
                    "query": arguments_without_time.query,
                    "tenants": arguments_without_time.tenants,
                    "timeframe": {
                        "from": arguments_without_time.timeframe_from,
                        "to": arguments_without_time.timeframe_to,
                    },
                }
            },
        )

        mock.post(
            url_result_query,
            status_code=200,
            json={"reply": {"err_code": 400}},
            additional_matcher=lambda request: request.json()
            == {
                "request_data": {
                    "query_id": "some-query-id",
                    "pending_flag": True,
                    "limit": 1000,
                    "format": "json",
                }
            },
        )

        with pytest.raises(ValueError):
            action.run(arguments_without_time)
