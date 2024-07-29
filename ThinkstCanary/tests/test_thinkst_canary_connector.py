from unittest.mock import MagicMock, patch

import pytest
import requests_mock

from thinkst_canary_modules import ThinkstCanaryModule
from thinkst_canary_modules.connector_thinkst_canary_alerts import ThinkstCanaryAlertsConnector


@pytest.fixture
def trigger(data_storage):
    module = ThinkstCanaryModule()
    trigger = ThinkstCanaryAlertsConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {"auth_token": "AUTH_TOKEN", "base_url": "https://example.com"}
    trigger.configuration = {"intake_key": "intake_key", "frequency": 60, "acknowledge": False}
    yield trigger


@pytest.fixture
def message1():
    return {
        "feed": "Unacknowledged Incidents",
        "incidents": [
            {
                "description": {
                    "acknowledged": "False",
                    "created": "1720684078",
                    "created_std": "2024-07-11 07:47:58 UTC+0000",
                    "description": "SSH Login Attempt",
                    "dst_host": "9.10.11.12",
                    "dst_host_public_ip": "",
                    "dst_port": "22",
                    "events": [
                        {
                            "LOCALVERSION": "SSH-2.0-MS_1.100",
                            "PASSWORD": "test",
                            "REMOTEVERSION": "SSH-2.0-libssh2_1.10.1_DEV",
                            "USERNAME": "azureuser",
                            "timestamp": 1720684078,
                            "timestamp_std": "2024-07-11 07:47:58 UTC+0000",
                        },
                        {
                            "LOCALVERSION": "SSH-2.0-MS_1.100",
                            "PASSWORD": "test",
                            "REMOTEVERSION": "SSH-2.0-libssh2_1.10.1_DEV",
                            "USERNAME": "azureuser",
                            "timestamp": 1720684081,
                            "timestamp_std": "2024-07-11 07:48:01 UTC+0000",
                        },
                    ],
                    "events_count": "2",
                    "events_list": "1720684078,1720684081",
                    "flock_id": "flock:default",
                    "flock_name": "Default Flock",
                    "ip_address": "",
                    "ippers": "",
                    "local_time": "2024-07-11 07:47:51",
                    "logtype": "4002",
                    "mac_address": "",
                    "matched_annotations": {},
                    "name": "thinkst-canary",
                    "node_id": "node-id-2",
                    "notified": "False",
                    "src_host": "5.6.7.8",
                    "src_host_reverse": "example.com",
                    "src_port": "53804",
                },
                "hash_id": "e35d196cf3ff157908b542a401810413",
                "id": "incident:sshlogin:11cdf5d57170cc4d057c8a4ef1a81d65:5.6.7.8:1720684078",
                "summary": "SSH Login Attempt",
                "updated": "Thu, 11 Jul 2024 07:48:01 GMT",
                "updated_id": 2,
                "updated_std": "2024-07-11 07:48:01 UTC+0000",
                "updated_time": "1720684081",
            },
            {
                "description": {
                    "acknowledged": "False",
                    "created": "1720684212",
                    "created_std": "2024-07-11 07:50:12 UTC+0000",
                    "description": "Canarytoken triggered",
                    "dst_host": "1.1.1.1",
                    "dst_port": "80",
                    "events": [
                        {
                            "canarytoken": "node-id-1",
                            "dst_port": 80,
                            "geoip": {
                                "city": "Emerainville",
                                "continent_code": "EU",
                                "country": "France",
                                "country_code": "FR",
                                "country_code3": "FRA",
                                "currency_code": "EUR",
                                "host_domain": "",
                                "hostname": "",
                                "ip": "1.2.3.4",
                                "is_bogon": False,
                                "is_v4_mapped": False,
                                "is_v6": False,
                                "latitude": 48.81276,
                                "longitude": 2.62139,
                                "region": "Ile-de-France",
                                "region_code": "J",
                                "timezone": {
                                    "abbr": "CEST",
                                    "date": "2024-07-11",
                                    "id": "Europe/Paris",
                                    "name": "Central European Summer Time",
                                    "offset": "+02:00",
                                    "time": "09:50:16.622847",
                                },
                                "valid": True,
                            },
                            "headers": {"Accept": "*/*", "Host": "example.com", "User-Agent": "curl/8.7.1"},
                            "ip_blocklist": {"is_proxy": False, "is_tor": False, "is_vpn": False},
                            "request_args": {},
                            "src_host": "1.2.3.4",
                            "timestamp": 1720684212,
                            "timestamp_std": "2024-07-11 07:50:12 UTC+0000",
                            "type": "http",
                        }
                    ],
                    "events_count": "1",
                    "events_list": "1720684212",
                    "flock_id": "flock:default",
                    "flock_name": "Default Flock",
                    "local_time": "2024-07-11 07:50:12 (UTC)",
                    "logtype": "17000",
                    "matched_annotations": {},
                    "memo": "Link to generate alert",
                    "name": "N/A",
                    "node_id": "node-id-1",
                    "notified": "False",
                    "src_host": "1.2.3.4",
                    "src_port": "0",
                },
                "hash_id": "f1b75ac7689ff88e1ecc40c84b115785",
                "id": "incident:canarytoken:23ea21520d2dbd87dd99b5e68ded0647:1.2.3.4:1720684212",
                "summary": "Canarytoken triggered",
                "updated": "Thu, 11 Jul 2024 07:50:12 GMT",
                "updated_id": 3,
                "updated_std": "2024-07-11 07:50:12 UTC+0000",
                "updated_time": "1720684212",
            },
        ],
        "max_updated_id": 3,
        "result": "success",
        "updated": "Thu, 11 Jul 2024 07:50:12 GMT",
        "updated_std": "2024-07-11 07:50:12 UTC+0000",
        "updated_timestamp": 1720684212,
    }


def test_fetch_events(trigger, message1):
    trigger.push_events_to_intakes = MagicMock()

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get("https://example.com/api/v1/incidents/unacknowledged", status_code=200, json=message1)
        events = trigger.fetch_events()

        assert list(events) == [trigger.extract_events(message1)]
        assert trigger.from_id == 3


def test_long_next_batch_should_not_sleep(trigger, message1):
    with patch(
        "thinkst_canary_modules.connector_thinkst_canary_alerts.time"
    ) as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/api/v1/incidents/unacknowledged",
            status_code=200,
            json=message1,
        )
        batch_duration = trigger.configuration.frequency + 20  # the batch lasts more than the frequency
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 0


def test_next_batch_sleep_until_next_round(trigger, message1):
    with patch(
        "thinkst_canary_modules.connector_thinkst_canary_alerts.time"
    ) as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/api/v1/incidents/unacknowledged",
            status_code=200,
            json=message1,
        )
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 1


def test_acknowledge_messages(trigger, message1):
    trigger.configuration.acknowledge = True

    with patch(
        "thinkst_canary_modules.connector_thinkst_canary_alerts.time"
    ) as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/api/v1/incidents/unacknowledged",
            status_code=200,
            json=message1,
        )

        url_ack = "https://example.com/api/v1/incident/acknowledge"
        mock_requests.post(url_ack, status_code=200)

        trigger.next_batch()
        ack_requests = [item.url for item in mock_requests.request_history if url_ack in item.url]

        assert len(ack_requests) == 2  # 1 for each incident
        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 1
