import pytest
from unittest.mock import MagicMock, patch
import requests_mock
from datetime import datetime, timedelta, timezone

from workday.connector import WorkdayConnector
from workday.endpoint import WorkdayEndpoint
from workday.client import WorkdayApiClient

@pytest.fixture
def trigger(data_storage):
    module = WorkdayApiClient(
        workday_host="wd2-impl-services1.workday.com",
        tenant_name="mytenant",
        client_id="clientid",
        client_secret="secret",
        refresh_token="refresh",
        token_endpoint="https://wd2-impl-services1.workday.com/token",
    )
    trigger = WorkdayConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = {"frequency": 1}
    yield trigger

@pytest.fixture
def workday_page_1():
    return [
        {"taskId": "1", "requestTime": "2025-11-20T10:00:00Z"}
    ]

@pytest.fixture
def workday_page_2():
    return [
        {"taskId": "2", "requestTime": "2025-11-20T10:01:00Z"}
    ]

def test_next_batch_multiple_pages(trigger, workday_page_1, workday_page_2):
    worker = WorkdayEndpoint(connector=trigger)
    worker.chunk_size = 1

    with requests_mock.Mocker() as m, patch("workday_modules.workday_endpoint.time.sleep") as mock_sleep:
        url = f"https://{trigger.module.configuration['workday_host']}/ccx/api/privacy/v1/{trigger.module.configuration['tenant_name']}/activityLogging"
        m.get(url, [
            {"json": workday_page_1},
            {"json": workday_page_2},
            {"json": []},
        ])

        worker.next_batch()
        # Should push 2 events (from 2 pages)
        assert trigger.push_events_to_intakes.call_count == 2
        assert mock_sleep.called

def test_next_batch_no_events(trigger):
    worker = WorkdayEndpoint(connector=trigger)
    with requests_mock.Mocker() as m, patch("workday_modules.workday_endpoint.time.sleep") as mock_sleep:
        url = f"https://{trigger.module.configuration['workday_host']}/ccx/api/privacy/v1/{trigger.module.configuration['tenant_name']}/activityLogging"
        m.get(url, [{"json": []}])
        worker.next_batch()
        # No events to push
        assert trigger.push_events_to_intakes.call_count == 0
        assert mock_sleep.called
