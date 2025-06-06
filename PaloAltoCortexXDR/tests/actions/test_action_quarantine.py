from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, call, patch

import orjson
import pytest
import requests_mock
from freezegun import freeze_time
from requests.exceptions import HTTPError
from sekoia_automation.storage import PersistentJSON

from cortex_module.actions.action_comment_alert import CommentAlertAction, CommentAlertArguments
from cortex_module.actions.action_quarantine import QuarantineAction, QuarantineArguments
from cortex_module.base import CortexModule
from cortex_module.cortex_edr_connector import CortexQueryEDRTrigger
from cortex_module.helper import handle_fqdn


@pytest.fixture
def action(module, symphony_storage):
    action = QuarantineAction(module=module, data_path=symphony_storage)

    action.log_exception = Mock()
    action.log = Mock()

    return action


@pytest.fixture
def arguments_0() -> QuarantineArguments:
    """
    file_path: str
    file_hash: str | None = None
    endpoint_ids: list[str] | None = None
    """
    return QuarantineArguments(
        file_path="C:\\<file path>\\test_x64.msi",
    )


@pytest.fixture
def arguments_1() -> QuarantineArguments:
    return QuarantineArguments(
        file_path="C:\\<file path>\\test_x64.msi",
        file_hash="1234567890",
        endpoint_ids=["0987654321"],
    )


@pytest.fixture
def arguments_2() -> QuarantineArguments:
    return QuarantineArguments(
        file_path="C:\\<file path>\\test_x64.msi",
        file_hash="1234567890",
    )


@pytest.fixture
def arguments_3() -> QuarantineArguments:
    return QuarantineArguments(
        file_path="C:\\<file path>\\test_x64.msi",
        endpoint_ids=["0987654321"],
    )


def test_run_action(action, arguments_0, arguments_1, arguments_2, arguments_3):
    fqdn = action.module.configuration.fqdn
    url = f"https://api-{fqdn}/public_api/v1/endpoints/quarantine"

    with requests_mock.Mocker() as mock:
        mock.post(
            url,
            status_code=200,
            json={"result": "123"},
            additional_matcher=lambda request: request.json()
            == {
                "request_data": {
                    "file_path": arguments_0.file_path,
                }
            },
        )

        assert action.run(arguments_0.dict()) == {"result": "123"}

        mock.post(
            url,
            status_code=200,
            json={"result": "123"},
            additional_matcher=lambda request: request.json()
            == {
                "request_data": {
                    "file_path": arguments_1.file_path,
                    "file_hash": arguments_1.file_hash,
                    "filters": {
                        "field": "endpoint_id_list",
                        "operator": "in",
                        "value": arguments_1.endpoint_ids,
                    },
                }
            },
        )

        assert action.run(arguments_1.dict()) == {"result": "123"}

        mock.post(
            url,
            status_code=200,
            json={"result": "123"},
            additional_matcher=lambda request: request.json()
            == {
                "request_data": {
                    "file_path": arguments_2.file_path,
                    "file_hash": arguments_2.file_hash,
                }
            },
        )
        assert action.run(arguments_2.dict()) == {"result": "123"}

        mock.post(
            url,
            status_code=200,
            json={"result": "123"},
            additional_matcher=lambda request: request.json()
            == {
                "request_data": {
                    "file_path": arguments_3.file_path,
                    "filters": {
                        "field": "endpoint_id_list",
                        "operator": "in",
                        "value": arguments_3.endpoint_ids,
                    },
                }
            },
        )
        assert action.run(arguments_3.dict()) == {"result": "123"}
