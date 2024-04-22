from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests_mock
from requests import Request, Response

from ubika_modules import UbikaModule
from ubika_modules.connector_ubika_cloud_protector_alerts import UbikaCloudProtectorAlertsConnector
from ubika_modules.connector_ubika_cloud_protector_base import FetchEventsException


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
    trigger = UbikaCloudProtectorAlertsConnector(module=module, data_path=data_storage)
    # mock the log function of trigger that requires network access to the api for reporting
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
                "application_id": "www.some-app.com",
                "id": "4.1.4.0",
                "reason": "module_name == 'eaccess' and event.SECURITY_URL == '/phpinfo.php' and "
                "event.SECURITY_ATTACKID == '10527-0 ' and tokens['http_ea__block_reason'] == "
                "'http_blacklist' and tokens['http_ea__block_part'] == 'uri' and tokens["
                "'http_ea_bl__is_custom_rule'] == False and tokens['http_ea_seclist__is_combine_rule'] == "
                "False and tokens['http_ea_seclist__is_virtual_patching'] == False",
                "http_method": "GET",
                "rule_id": "10527-0 ",
                "attack_family": "Information Disclosure",
                "ip_source": "1.2.3.4",
                "traffic_id": "ZhVpbQoAQi8AAE2yAksAAAAA",
                "path": "/phpinfo.php",
                "timestamp": 1712679277,
            },
            {
                "application_id": "www.some-app.com",
                "id": "4.1.4.0",
                "reason": "module_name == 'eaccess' and event.SECURITY_URL == '/phpinfo.php' and "
                "event.SECURITY_ATTACKID == '10527-0 ' and tokens['http_ea__block_reason'] == "
                "'http_blacklist' and tokens['http_ea__block_part'] == 'uri' and tokens["
                "'http_ea_bl__is_custom_rule'] == False and tokens['http_ea_seclist__is_combine_rule'] == "
                "False and tokens['http_ea_seclist__is_virtual_patching'] == False",
                "http_method": "GET",
                "rule_id": "10527-0 ",
                "attack_family": "Information Disclosure",
                "ip_source": "1.2.3.4",
                "traffic_id": "ZhVp6AoAQi8AAE20AkwAAABD",
                "path": "/phpinfo.php",
                "timestamp": 1712679400,
            },
            {
                "application_id": "www.some-app.com",
                "id": "4.1.4.0",
                "reason": "module_name == 'eaccess' and event.SECURITY_URL == '/phpinfo.php' and "
                "event.SECURITY_ATTACKID == '10527-0 ' and tokens['http_ea__block_reason'] == "
                "'http_blacklist' and tokens['http_ea__block_part'] == 'uri' and tokens["
                "'http_ea_bl__is_custom_rule'] == False and tokens['http_ea_seclist__is_combine_rule'] == "
                "False and tokens['http_ea_seclist__is_virtual_patching'] == False",
                "http_method": "GET",
                "rule_id": "10527-0 ",
                "attack_family": "Information Disclosure",
                "ip_source": "1.2.3.4",
                "traffic_id": "ZhVp6goAQi8AAE2yAkwAAAAB",
                "path": "/phpinfo.php",
                "timestamp": 1712679402,
            },
            {
                "application_id": "www.some-app.com",
                "id": "4.1.4.0",
                "reason": "module_name == 'eaccess' and event.SECURITY_URL == '/phpinfo.php' and "
                "event.SECURITY_ATTACKID == '10527-0 ' and tokens['http_ea__block_reason'] == "
                "'http_blacklist' and tokens['http_ea__block_part'] == 'uri' and tokens["
                "'http_ea_bl__is_custom_rule'] == False and tokens['http_ea_seclist__is_combine_rule'] == "
                "False and tokens['http_ea_seclist__is_virtual_patching'] == False",
                "http_method": "GET",
                "rule_id": "10527-0 ",
                "attack_family": "Information Disclosure",
                "ip_source": "1.2.3.4",
                "traffic_id": "ZhVp7QoAQi8AAE20Ak4AAABE",
                "path": "/phpinfo.php",
                "timestamp": 1712679405,
            },
        ],
        "cursor": "2024-04-09T16:16:46.156145919Z",
    }


@pytest.fixture
def message2():
    return {"items": []}


def test_fetch_events_with_pagination(trigger, message1, message2):
    with requests_mock.Mocker() as mock_requests, patch(
        "ubika_modules.connector_ubika_cloud_protector_base.time"
    ) as mock_time:
        mock_time.sleep = MagicMock()
        mock_requests.get(
            "https://eu-west-2.cloudprotector.com/api/v1/providers/provider1/tenants/tenant2/alertlogs?"
            "start_time=1667645999&limit=100",
            status_code=200,
            json=message1,
        )

        mock_requests.get(
            "https://eu-west-2.cloudprotector.com/api/v1/providers/provider1/tenants/tenant2/alertlogs?"
            "cursor=2024-04-09T16%3A16%3A46.156145919Z&limit=100",
            status_code=200,
            json=message2,
        )
        events = trigger.fetch_events()

        assert list(events) == [message1["items"]]
        assert trigger.from_date.isoformat() == "2024-04-09T16:16:46+00:00"


def test_next_batch_sleep_until_next_round(trigger, message1, message2):
    with requests_mock.Mocker() as mock_requests, patch(
        "ubika_modules.connector_ubika_cloud_protector_base.time"
    ) as mock_time:
        mock_time.sleep = MagicMock()

        mock_requests.get(
            "https://eu-west-2.cloudprotector.com/api/v1/providers/provider1/tenants/tenant2/alertlogs?"
            "start_time=1667645999&limit=100",
            status_code=200,
            json=message1,
        )

        mock_requests.get(
            "https://eu-west-2.cloudprotector.com/api/v1/providers/provider1/tenants/tenant2/alertlogs?"
            "cursor=2024-04-09T16%3A16%3A46.156145919Z&limit=100",
            status_code=200,
            json=message2,
        )

        batch_duration = trigger.configuration.frequency + 20  # the batch lasts more than the frequency
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 0


def test_handle_response_error(trigger):
    response = Response()
    response.request = Request()
    response.request.url = "https://sekoia.io"
    response.status_code = 500
    response.reason = "Internal Error"
    with pytest.raises(FetchEventsException) as m:
        trigger._handle_response_error(response)

    assert (
        str(m.value)
        == "Request on Ubika Cloud Protector Alerts API to fetch events failed with status 500 - Internal Error on https://sekoia.io"
    )
