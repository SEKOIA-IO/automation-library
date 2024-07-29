import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import requests_mock
from faker import Faker

from lacework_module.base import LaceworkModule
from lacework_module.client import LaceworkApiClient
from lacework_module.lacework_connector import LaceworkEventsTrigger


@pytest.fixture
def account(session_faker: Faker) -> str:
    return session_faker.word()


@pytest.fixture
def key_id(session_faker: Faker) -> str:
    return session_faker.word()


@pytest.fixture
def secret(session_faker: Faker) -> str:
    return session_faker.word()


@pytest.fixture
def intake_key(session_faker: Faker) -> str:
    return session_faker.word()


@pytest.fixture
def trigger(symphony_storage: Path, account: str, key_id: str, secret: str, intake_key: str):
    module = LaceworkModule()
    trigger = LaceworkEventsTrigger(module=module, data_path=symphony_storage)
    trigger.module.configuration = {
        "secret": secret,
        "key_id": key_id,
        "account": account,
    }
    trigger.configuration = {"intake_key": intake_key, "chunk_size": 1}
    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()

    return trigger


def test_get_next_events(trigger: LaceworkEventsTrigger, alerts_response: dict[str, any]):
    host = f"https://{trigger.module.configuration.account}"
    params = {"token": "foo-token", "expiresAt": str(datetime.utcnow() + timedelta(seconds=3600))}
    with requests_mock.Mocker() as mock:
        mock.post(
            url=f"{host}/api/v2/access/tokens",
            headers={"X-LW-UAKS": "secret_key", "Content-Type": "application/json"},
            json=params,
        )

        mock.get(url=f"{host}/api/v2/Alerts", status_code=200, headers=params, json=alerts_response)
        trigger.forward_next_batches()
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls) > 0


def test_get_next_events_1(
    trigger: LaceworkEventsTrigger,
    alerts_response: dict[str, Any],
    alerts_response_with_next: dict[str, Any],
    alerts_response_with_next_1: dict[str, Any],
):
    host = f"https://{trigger.module.configuration.account}"
    params = {"token": "foo-token", "expiresAt": str(datetime.utcnow() + timedelta(seconds=3600))}
    with requests_mock.Mocker() as mock:
        mock.post(
            url=f"{host}/api/v2/access/tokens",
            headers={"X-LW-UAKS": "secret_key", "Content-Type": "application/json"},
            json=params,
        )

        mock.get(url=f"{host}/api/v2/Alerts", status_code=200, headers=params, json=alerts_response_with_next)
        mock.get(
            url=LaceworkApiClient.get_next_page_url(alerts_response_with_next),
            status_code=200,
            json=alerts_response_with_next_1,
        )
        most_recent_time = datetime.utcnow().replace(tzinfo=timezone.utc)
        most_recent_alert_id = 855629 * 2
        mock.get(
            url=LaceworkApiClient.get_next_page_url(alerts_response_with_next_1),
            status_code=200,
            json={
                "data": [
                    {
                        "alertId": most_recent_alert_id,
                        "startTime": most_recent_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                        "alertType": "ChangedFile",
                        "severity": "Critical",
                        "internetExposure": "UnknownInternetExposure",
                        "reachability": "UnknownReachability",
                        "derivedFields": {"category": "Policy", "sub_category": "File", "source": "Agent"},
                        "endTime": most_recent_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                        "lastUserUpdatedTime": "2022-06-30T01:26:51.392Z",
                        "status": "Open",
                        "alertName": "Unauthorized API Call",
                        "alertInfo": {
                            "subject": "Unauthorized API Call: For account: `1234567890`: Unauthorized API call was attempted `4` times",
                            "description": "For account: 1234567890: Unauthorized API call was attempted 4 times by user  ABCD1234:Lacework",
                        },
                    },
                ]
            },
        )

        trigger.forward_next_batches()
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls) > 0

        assert trigger.latest_start_event_date == most_recent_time
        assert trigger.latest_alert_id == most_recent_alert_id


@pytest.mark.skipif("{'LACEWORK_ID', 'LACEWORK_SECRET'}.issubset(os.environ.keys()) == False")
def test_forward_next_batches_integration(symphony_storage: Path):
    module = LaceworkModule()
    trigger = LaceworkEventsTrigger(module=module, data_path=symphony_storage)
    trigger.configuration.account = (os.environ["LACEWORK_URL"],)
    trigger.configuration.key_id = (os.environ["LACEWORK_ACCESS_KEY"],)
    trigger.configuration.secret = (os.environ["LACEWORK_SECRET_KEY"],)
    trigger.configuration.frequency = 0
    trigger.configuration.intake_key = "0123456789"
    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()
    trigger.forward_next_batches()
    calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
    assert len(calls) > 0
