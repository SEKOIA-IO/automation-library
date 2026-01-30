from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest
from respx import MockRouter
from sekoia_automation.storage import PersistentJSON

from ubika_modules import UbikaModule
from ubika_modules.connector_ubika_cloud_protector_traffic import UbikaCloudProtectorTrafficConnector


@pytest.fixture
def fake_time():
    yield datetime(2022, 11, 5, 11, 59, 59, tzinfo=timezone.utc)


@pytest.fixture
def patch_datetime_now(fake_time):
    with patch("ubika_modules.connector_ubika_cloud_protector_base.datetime") as mock_datetime:
        mock_datetime.now.return_value = fake_time
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        mock_datetime.fromtimestamp = lambda ts: datetime.fromtimestamp(ts)
        yield mock_datetime


@pytest.fixture
def trigger(data_storage, patch_datetime_now):
    module = UbikaModule()
    trigger = UbikaCloudProtectorTrafficConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = {
        "provider": "provider1",
        "tenant": "tenant2",
        "token": "some_token_here",
        "intake_key": "intake_key",
        "chunk_size": 100,
    }
    yield trigger


@pytest.fixture
def message1():
    return {
        "items": [
            {
                "id": "ZhVpSAoAQi8AAE20AkoAAABB",
                "application_id": "www.some-app.com",
                "ip_source": "1.2.3.4",
                "http_method": "GET",
                "protocol": "HTTP/1.1",
                "hostname": "www.some-app.com.289339716950101.app.d.eu-west-2.cloudprotector.com",
                "path": "/",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "x_forwarded_for": "1.2.3.4",
                "http_status_code": 200,
                "response_size": 633,
                "total_response_time": 35,
                "timestamp": 1712679406,
            },
        ],
        "cursor": "2024-04-09T16:16:46.691879210Z",
    }


@pytest.fixture
def message2():
    return {"items": []}


@pytest.mark.respx(base_url="https://eu-west-2.cloudprotector.com")
def test_fetch_events_with_pagination(respx_mock: MockRouter, trigger, message1, message2):
    with patch("ubika_modules.connector_ubika_cloud_protector_base.time") as mock_time:
        mock_time.sleep = MagicMock()

        respx_mock.get(
            "/api/v1/providers/provider1/tenants/tenant2/trafficlogs",
            params={"start_time": "1667645999", "limit": "100"},
        ).mock(return_value=httpx.Response(200, json=message1))

        respx_mock.get(
            "/api/v1/providers/provider1/tenants/tenant2/trafficlogs?"
            "cursor=2024-04-09T16%3A16%3A46.691879210Z&limit=100"
        ).mock(return_value=httpx.Response(200, json=message2))

        events = trigger.fetch_events()

        assert list(events) == [message1["items"]]
        assert trigger.from_date.isoformat() == "2024-04-09T16:16:47+00:00"


def test_load_without_checkpoint(trigger, data_storage, fake_time):
    context = PersistentJSON("context.json", data_storage)

    with context as cache:
        cache["most_recent_date_seen"] = None

    datetime_expected = fake_time - timedelta(hours=1)

    assert trigger.most_recent_date_seen.isoformat() == datetime_expected.isoformat()


def test_old_checkpoint(trigger, data_storage, fake_time):
    context = PersistentJSON("context.json", data_storage)

    with context as cache:
        cache["most_recent_date_seen"] = "2022-02-22T16:16:46+00:00"

    datetime_expected = fake_time - timedelta(days=7)
    assert trigger.most_recent_date_seen.isoformat() == datetime_expected.isoformat()
