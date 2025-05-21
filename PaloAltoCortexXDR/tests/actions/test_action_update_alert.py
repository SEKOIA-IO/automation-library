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
from cortex_module.base import CortexModule
from cortex_module.cortex_edr_connector import CortexQueryEDRTrigger
from cortex_module.helper import handle_fqdn


@pytest.fixture
def action(module, symphony_storage):
    action = UpdateAlertAction(module=module, data_path=symphony_storage)

    action.log_exception = Mock()
    action.log = Mock()

    return action


@pytest.fixture
def arguments() -> UpdateAlertArguments:
    return UpdateAlertArguments(
        alert_id_list=["1234567890", "0987654321"],
        severity=Severity.LOW,
        status=Status.RESOLVED_OTHER,
    )


def test_run_action(action, arguments):
    fqdn = action.module.configuration.fqdn
    url = f"https://api-{fqdn}/public_api/v1/alerts/update_alerts"

    with requests_mock.Mocker() as mock:
        mock.post(
            url,
            status_code=200,
            json={"result": "123"},
            additional_matcher=lambda request: request.json()
            == {
                "request_data": {
                    "alert_id_list": ["1234567890", "0987654321"],
                    "update_data": {"severity": "low", "status": "resolved_other"},
                }
            },
        )

        assert action.run(arguments) == {"result": "123"}
