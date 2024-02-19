import os
from pathlib import Path
from unittest.mock import MagicMock, Mock
from datetime import datetime, timedelta

import pytest
import requests_mock

from lacework_module.base import LaceworkConfiguration, LaceworkModule
from lacework_module.lacework_connector import LaceworkConfiguration, LaceworkEventsTrigger


@pytest.fixture
def trigger(symphony_storage: Path):
    module = LaceworkModule()
    trigger = LaceworkEventsTrigger(module=module, data_path=symphony_storage)
    trigger.module.configuration = {
        "secret_key": "my-secret",
        "access_key": "my-id",
        "lacework_url": "api"
    }
    trigger.configuration = {
        "intake_key": "0123456789",
    }
    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()
    return trigger


def test_get_next_events(trigger: LaceworkEventsTrigger):
    host = f"https://{trigger.module.configuration.lacework_url}.lacework.net"
    params= {
              "token": "foo-token",
              "expiresAt": str(datetime.utcnow() + timedelta(seconds=3600))
            }
    with requests_mock.Mocker() as mock:
        mock.post(
            url=f"{host}/api/v2/access/tokens",
            headers={
                    "X-LW-UAKS": "secret_key",
                    "Content-Type": "application/json"
                },
            json=params
        )

        # flake8: noqa

        response = {
          "paging": {
            "rows": 1000,
            "totalRows": 3120,
            "urls": {
              "nextPage": "https://api-test.lacework.net/api/v2/Alerts/AbcdEfgh123..."
            }
          },
          "data": [
            {
              "alertId": 855628,
              "startTime": "2022-06-30T00:00:00.000Z",
              "alertType": "MaliciousFile",
              "severity": "Critical",
              "internetExposure": "UnknownInternetExposure",
              "reachability": "UnknownReachability",
              "derivedFields": {
                "category": "Anomaly",
                "sub_category": "File",
                "source": "Agent"
              },
              "endTime": "2022-06-30T01:00:00.000Z",
              "lastUserUpdatedTime": "",
              "status": "Open",
              "alertName": "Clone of Cloud Activity log ingestion failure detected",
              "alertInfo": {
                "subject": "Clone of Cloud Activity log ingestion failure detected: `azure-al-india-dnd` (and `3` more) is failing for data ingestion into Lacework",
                "description": "New integration failure detected for azure-al-india-dnd (and 3 more)"
              },
              "policyId": "CUSTOM_PLATFORM_130"
            },
            {
              "alertId": 855629,
              "startTime": "2022-06-30T00:00:00.000Z",
              "alertType": "ChangedFile",
              "severity": "Critical",
              "internetExposure": "UnknownInternetExposure",
              "reachability": "UnknownReachability",
              "derivedFields": {
                "category": "Policy",
                "sub_category": "File",
                "source": "Agent"
              },
              "endTime": "2022-06-30T01:00:00.000Z",
              "lastUserUpdatedTime": "2022-06-30T01:26:51.392Z",
              "status": "Open",
              "alertName": "Unauthorized API Call",
              "alertInfo": {
                "subject": "Unauthorized API Call: For account: `1234567890`: Unauthorized API call was attempted `4` times",
                "description": "For account: 1234567890: Unauthorized API call was attempted 4 times by user  ABCD1234:Lacework"
              }
            }
          ]
        }
        # flake8: qa

        mock.get(
            url=f"{host}/api/v2/Alerts",
            status_code=200,
            headers=params,
            json=response
        )
        trigger.forward_next_batches()
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls) > 0

@pytest.mark.skipif("{'LACEWORK_ID', 'LACEWORK_SECRET'}.issubset(os.environ.keys()) == False")
def test_forward_next_batches_integration(symphony_storage: Path):
    module = LaceworkModule()
    trigger = LaceworkEventsTrigger(module=module, data_path=symphony_storage)
    trigger.module.configuration = {
        "lacework_url": os.environ["LACEWORK_URL"],
        "access_key": os.environ["LACEWORK_ACCESS_KEY"],
        "secret_key": os.environ["LACEWORK_SECRET_KEY"]
    }
    trigger.configuration = {"frequency": 0, "intake_key": "0123456789"}
    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()
    trigger.forward_next_batches()
    calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
    assert len(calls) > 0