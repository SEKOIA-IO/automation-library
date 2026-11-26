from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import orjson
import pytest
import requests
import requests_mock

from thinkst_canary_modules import ThinkstCanaryModule
from thinkst_canary_modules.connector_thinkst_canary_alerts import API_TIMEOUT_SECONDS, ThinkstCanaryAlertsConnector


def build_connector(data_storage):
    module = ThinkstCanaryModule()
    trigger = ThinkstCanaryAlertsConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {"auth_token": "AUTH_TOKEN", "base_url": "https://example.com"}
    trigger.configuration = {"intake_key": "intake_key", "frequency": 60, "acknowledge": False}
    return trigger


@pytest.fixture
def trigger(data_storage):
    yield build_connector(data_storage)


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
        mock_requests.get("https://example.com/api/v1/incidents/all", status_code=200, json=message1)
        events = trigger.fetch_events()

        assert list(events) == [trigger.extract_events(message1)]
        assert trigger.from_id == 3


def test_long_next_batch_should_not_sleep(trigger, message1):
    with patch(
        "thinkst_canary_modules.connector_thinkst_canary_alerts.time"
    ) as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/api/v1/incidents/all",
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
            "https://example.com/api/v1/incidents/all",
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
            "https://example.com/api/v1/incidents/all",
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


URL_INCIDENTS = "https://example.com/api/v1/incidents/all"
BAD_GATEWAY = {"status_code": 502, "text": "<html><body>Bad Gateway</body></html>"}


def test_next_batch_should_handle_5xx_errors(trigger):
    with (
        patch("thinkst_canary_modules.connector_thinkst_canary_alerts.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(URL_INCIDENTS, **BAD_GATEWAY)
        mock_time.time.side_effect = [0.0, 1.0]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 0
        trigger.log.assert_any_call(level="error", message="failed to fetch events")
        assert mock_time.sleep.call_count == 1  # the polling delay is still respected


def test_next_batch_should_recover_after_5xx_error(trigger, message1):
    with (
        patch("thinkst_canary_modules.connector_thinkst_canary_alerts.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(URL_INCIDENTS, [BAD_GATEWAY, {"status_code": 200, "json": message1}])
        mock_time.time.side_effect = [0.0, 1.0, 60.0, 61.0]

        trigger.next_batch()
        assert trigger.push_events_to_intakes.call_count == 0

        trigger.next_batch()
        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_requests.call_count == 2


def test_fetch_pages_should_set_a_timeout_on_every_request(trigger, message1):
    first_page = deepcopy(message1)
    first_page["cursor"] = {"next": "next-page"}
    last_page = {"incidents": [], "cursor": {"next": None}}

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            URL_INCIDENTS, [{"status_code": 200, "json": first_page}, {"status_code": 200, "json": last_page}]
        )

        list(trigger.fetch_pages(None))

        assert len(mock_requests.request_history) == 2
        assert all(request.timeout == API_TIMEOUT_SECONDS for request in mock_requests.request_history)


def test_acknowledge_incident_should_set_a_timeout(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post("https://example.com/api/v1/incident/acknowledge", status_code=200)

        trigger.acknowledge_incident(incident_id="incident:1")

        assert mock_requests.request_history[0].timeout == API_TIMEOUT_SECONDS


def test_next_batch_should_raise_on_timeout_and_keep_the_cursor(trigger):
    with (
        patch("thinkst_canary_modules.connector_thinkst_canary_alerts.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(URL_INCIDENTS, exc=requests.exceptions.ReadTimeout)
        mock_time.time.side_effect = [0.0, 1.0]

        with pytest.raises(requests.exceptions.ReadTimeout):
            trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 0
        assert trigger.from_id is None


def test_next_batch_should_forward_events_when_acknowledge_times_out(trigger, message1):
    trigger.configuration.acknowledge = True

    with (
        patch("thinkst_canary_modules.connector_thinkst_canary_alerts.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(URL_INCIDENTS, status_code=200, json=message1)
        mock_requests.post("https://example.com/api/v1/incident/acknowledge", exc=requests.exceptions.ReadTimeout)
        mock_time.time.side_effect = [0.0, 1.0]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert trigger.from_id == 3
        assert trigger.log_exception.call_count == 1


def test_next_batch_should_save_the_cursor_only_for_forwarded_pages(trigger, message1):
    first_page = deepcopy(message1)
    first_page["cursor"] = {"next": "next-page"}
    second_page = deepcopy(message1)
    second_page["max_updated_id"] = 5
    for incident in second_page["incidents"]:
        incident["id"] = f"{incident['id']}:new"
    trigger.push_events_to_intakes.side_effect = [None, RuntimeError("intake unavailable")]

    with (
        patch("thinkst_canary_modules.connector_thinkst_canary_alerts.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(
            URL_INCIDENTS, [{"status_code": 200, "json": first_page}, {"status_code": 200, "json": second_page}]
        )
        mock_time.time.side_effect = [0.0, 1.0]

        with pytest.raises(RuntimeError):
            trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 2
        assert trigger.from_id == 3
        with trigger.context as cache:
            assert cache["most_recent_id_seen"] == 3


def test_extract_events_should_remove_event_counters(message1):
    records = ThinkstCanaryAlertsConnector.extract_events(message1)

    assert not any("events_count" in record or "events_list" in record for record in records)


def test_extract_events_should_accept_incidents_without_event_counters(message1):
    expected_count = sum(1 + len(incident["description"]["events"]) for incident in message1["incidents"])
    for incident in message1["incidents"]:
        del incident["description"]["events_count"]
        del incident["description"]["events_list"]

    records = ThinkstCanaryAlertsConnector.extract_events(message1)

    assert len(records) == expected_count
    assert not any("events_count" in record or "events_list" in record for record in records)


def test_extract_events_should_return_only_the_incident_when_it_has_no_events():
    page = {
        "incidents": [
            {
                "id": "incident:disconnect:1",
                "summary": "Canary Disconnected",
                "updated_time": "1720684212",
                "description": {"description": "Canary Disconnected"},
            }
        ]
    }

    assert ThinkstCanaryAlertsConnector.extract_events(page) == [
        {
            "incident_id": "incident:disconnect:1",
            "event_type": "incident",
            "summary": "Canary Disconnected",
            "timestamp": "1720684212",
        }
    ]


URL_ACKNOWLEDGE = "https://example.com/api/v1/incident/acknowledge"


def make_page(incidents: list[dict], max_updated_id: int, next_cursor: str | None = None) -> dict:
    return {
        "feed": "All Incidents",
        "incidents": deepcopy(incidents),
        "max_updated_id": max_updated_id,
        "cursor": {"next": next_cursor},
        "result": "success",
        "updated_std": "2024-07-11 07:50:12 UTC+0000",
    }


def acknowledged(incident: dict, updated_id: int) -> dict:
    incident = deepcopy(incident)
    incident["description"]["acknowledged"] = "True"
    incident["updated_id"] = updated_id
    return incident


def pushed_incident_ids(trigger) -> list[set[str]]:
    return [
        {orjson.loads(event)["incident_id"] for event in call.kwargs["events"]}
        for call in trigger.push_events_to_intakes.call_args_list
    ]


def test_fetch_pages_should_poll_all_incidents_since_the_saved_cursor(trigger, message1):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(URL_INCIDENTS, status_code=200, json=message1)

        list(trigger.fetch_pages(3))

        assert mock_requests.request_history[0].path == "/api/v1/incidents/all"
        assert mock_requests.request_history[0].qs == {"limit": ["1000"], "incidents_since": ["3"]}


def test_fetch_pages_should_bound_the_first_run_lookback(trigger, message1):
    with (
        patch("thinkst_canary_modules.connector_thinkst_canary_alerts.datetime") as mock_datetime,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_datetime.now.return_value = datetime(2024, 7, 11, 8, 0, 0, tzinfo=timezone.utc)
        mock_requests.get(URL_INCIDENTS, status_code=200, json=message1)

        list(trigger.fetch_pages(None))

        assert mock_requests.request_history[0].path == "/api/v1/incidents/all"
        assert mock_requests.request_history[0].qs == {"limit": ["1000"], "newer_than": ["2024-07-10-08:00:00"]}


def test_fetch_events_should_follow_the_pagination_cursor(trigger, message1):
    ssh_incident, token_incident = message1["incidents"]
    first_page = make_page([ssh_incident], max_updated_id=2, next_cursor="next-page")
    second_page = make_page([token_incident], max_updated_id=3)

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(URL_INCIDENTS, [{"json": first_page}, {"json": second_page}])

        batches = list(trigger.fetch_events())

        assert mock_requests.request_history[1].qs == {"cursor": ["next-page"]}

    assert [{event["incident_id"] for event in batch} for batch in batches] == [
        {ssh_incident["id"]},
        {token_incident["id"]},
    ]
    assert trigger.from_id == 3


def test_next_batch_should_forward_an_incident_acknowledged_before_being_collected(trigger, message1):
    ssh_incident = message1["incidents"][0]

    with (
        patch("thinkst_canary_modules.connector_thinkst_canary_alerts.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(URL_INCIDENTS, json=make_page([acknowledged(ssh_incident, 2)], max_updated_id=2))
        mock_time.time.side_effect = [0.0, 1.0]

        trigger.next_batch()

    assert pushed_incident_ids(trigger) == [{ssh_incident["id"]}]


def test_next_batch_should_not_forward_again_an_incident_only_acknowledged(trigger, message1):
    ssh_incident, token_incident = message1["incidents"]
    second_poll = make_page([acknowledged(ssh_incident, 4), acknowledged(token_incident, 5)], max_updated_id=5)

    with (
        patch("thinkst_canary_modules.connector_thinkst_canary_alerts.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(URL_INCIDENTS, [{"json": deepcopy(message1)}, {"json": second_poll}])
        mock_time.time.side_effect = [0.0, 1.0, 60.0, 61.0]

        trigger.next_batch()
        trigger.next_batch()

        assert mock_requests.request_history[1].qs["incidents_since"] == ["3"]

    assert trigger.push_events_to_intakes.call_count == 1
    assert trigger.from_id == 5


def test_next_batch_should_forward_again_an_incident_with_new_events(trigger, message1):
    ssh_incident = message1["incidents"][0]
    updated_incident = deepcopy(ssh_incident)
    updated_incident["updated_id"] = 4
    updated_incident["description"]["events"].append({"USERNAME": "root", "timestamp": 1720684090})

    with (
        patch("thinkst_canary_modules.connector_thinkst_canary_alerts.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(
            URL_INCIDENTS,
            [{"json": make_page([ssh_incident], max_updated_id=2)}, {"json": make_page([updated_incident], 4)}],
        )
        mock_time.time.side_effect = [0.0, 1.0, 60.0, 61.0]

        trigger.next_batch()
        trigger.next_batch()

    assert pushed_incident_ids(trigger) == [{ssh_incident["id"]}, {ssh_incident["id"]}]


def test_next_batch_should_remember_forwarded_incidents_across_restarts(trigger, message1, data_storage):
    ssh_incident = message1["incidents"][0]

    with (
        patch("thinkst_canary_modules.connector_thinkst_canary_alerts.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(
            URL_INCIDENTS,
            [
                {"json": make_page([ssh_incident], max_updated_id=2)},
                {"json": make_page([acknowledged(ssh_incident, 4)], max_updated_id=4)},
            ],
        )
        mock_time.time.side_effect = [0.0, 1.0, 60.0, 61.0]

        trigger.next_batch()
        restarted = build_connector(data_storage)
        restarted.next_batch()

    assert trigger.push_events_to_intakes.call_count == 1
    assert restarted.push_events_to_intakes.call_count == 0
    assert restarted.from_id == 4


def test_next_batch_should_bound_the_forwarded_incidents_memory(trigger, message1):
    ssh_incident, token_incident = message1["incidents"]
    second_poll = make_page([acknowledged(ssh_incident, 4), acknowledged(token_incident, 5)], max_updated_id=5)

    with (
        patch("thinkst_canary_modules.connector_thinkst_canary_alerts.MAX_FORWARDED_INCIDENTS", 1),
        patch("thinkst_canary_modules.connector_thinkst_canary_alerts.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(URL_INCIDENTS, [{"json": deepcopy(message1)}, {"json": second_poll}])
        mock_time.time.side_effect = [0.0, 1.0, 60.0, 61.0]

        trigger.next_batch()
        trigger.next_batch()

    # only the most recently forwarded incident is remembered: the oldest one is forwarded again
    assert pushed_incident_ids(trigger) == [{ssh_incident["id"], token_incident["id"]}, {ssh_incident["id"]}]


def test_acknowledge_should_skip_incidents_already_acknowledged(trigger, message1):
    trigger.configuration.acknowledge = True
    ssh_incident, token_incident = message1["incidents"]

    with (
        patch("thinkst_canary_modules.connector_thinkst_canary_alerts.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(URL_INCIDENTS, json=make_page([acknowledged(ssh_incident, 2), token_incident], 3))
        mock_requests.post(URL_ACKNOWLEDGE, status_code=200)
        mock_time.time.side_effect = [0.0, 1.0]

        trigger.next_batch()

        ack_requests = [request for request in mock_requests.request_history if request.method == "POST"]

    assert [request.qs["incident"] for request in ack_requests] == [[token_incident["id"]]]
    assert pushed_incident_ids(trigger) == [{ssh_incident["id"], token_incident["id"]}]


def test_next_batch_should_not_acknowledge_incidents_that_were_not_forwarded(trigger, message1):
    trigger.configuration.acknowledge = True
    trigger.push_events_to_intakes.side_effect = RuntimeError("intake unavailable")

    with (
        patch("thinkst_canary_modules.connector_thinkst_canary_alerts.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(URL_INCIDENTS, json=message1)
        mock_requests.post(URL_ACKNOWLEDGE, status_code=200)
        mock_time.time.side_effect = [0.0, 1.0]

        with pytest.raises(RuntimeError):
            trigger.next_batch()

        assert not any(request.method == "POST" for request in mock_requests.request_history)
