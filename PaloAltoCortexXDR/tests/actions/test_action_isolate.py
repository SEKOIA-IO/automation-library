from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, call, patch

import orjson
import pytest
import requests_mock
from freezegun import freeze_time
from requests.exceptions import HTTPError
from sekoia_automation.storage import PersistentJSON

from cortex_module.actions.action_comment_alert import CommentAlertAction, CommentAlertArguments
from cortex_module.actions.action_isolate import IsolateAction, IsolateArguments, UnisolateAction
from cortex_module.base import CortexModule
from cortex_module.cortex_edr_connector import CortexQueryEDRTrigger
from cortex_module.helper import handle_fqdn


@pytest.fixture
def isolate_action(module, symphony_storage):
    action = IsolateAction(module=module, data_path=symphony_storage)

    action.log_exception = Mock()
    action.log = Mock()

    return action


@pytest.fixture
def unisolate_action(module, symphony_storage):
    action = UnisolateAction(module=module, data_path=symphony_storage)

    action.log_exception = Mock()
    action.log = Mock()

    return action


@pytest.fixture
def arguments_0() -> IsolateArguments:
    return IsolateArguments(endpoint_id="1234567890")


@pytest.fixture
def arguments_1() -> IsolateArguments:
    return IsolateArguments(
        endpoint_id="1234567890",
        incident_id="0987654321",
    )


def test_run_isolate_action(isolate_action, arguments_0, arguments_1):
    fqdn = isolate_action.module.configuration.fqdn
    url = f"https://api-{fqdn}/public_api/v1/endpoints/isolate"

    with requests_mock.Mocker() as mock:
        mock.post(
            url,
            status_code=200,
            json={"result": "123"},
            additional_matcher=lambda request: request.json()
            == {
                "request_data": {
                    "endpoint_id": arguments_0.endpoint_id,
                }
            },
        )

        assert isolate_action.run(arguments_0) == {"result": "123"}

        mock.post(
            url,
            status_code=200,
            json={"result": "345"},
            additional_matcher=lambda request: request.json()
            == {
                "request_data": {
                    "endpoint_id": arguments_1.endpoint_id,
                    "incident_id": arguments_1.incident_id,
                }
            },
        )

        assert isolate_action.run(arguments_1) == {"result": "345"}


def test_run_unisolate_action(unisolate_action, arguments_0, arguments_1):
    fqdn = unisolate_action.module.configuration.fqdn
    url = f"https://api-{fqdn}/public_api/v1/endpoints/unisolate"

    with requests_mock.Mocker() as mock:
        mock.post(
            url,
            status_code=200,
            json={"result": "123"},
            additional_matcher=lambda request: request.json()
            == {
                "request_data": {
                    "endpoint_id": arguments_0.endpoint_id,
                }
            },
        )

        assert unisolate_action.run(arguments_0) == {"result": "123"}

        mock.post(
            url,
            status_code=200,
            json={"result": "345"},
            additional_matcher=lambda request: request.json()
            == {
                "request_data": {
                    "endpoint_id": arguments_1.endpoint_id,
                    "incident_id": arguments_1.incident_id,
                }
            },
        )

        assert unisolate_action.run(arguments_1) == {"result": "345"}
