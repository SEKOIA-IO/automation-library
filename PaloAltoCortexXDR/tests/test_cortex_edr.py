from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, call, patch

import orjson
import pytest
import requests_mock
from freezegun import freeze_time
from requests.exceptions import HTTPError
from sekoia_automation.storage import PersistentJSON

from cortex_module.base import CortexModule
from cortex_module.cortex_edr_connector import CortexQueryEDRTrigger
from cortex_module.helper import handle_fqdn


@pytest.fixture
def trigger(module, symphony_storage):
    trigger = CortexQueryEDRTrigger(module=module, data_path=symphony_storage)
    trigger.configuration = {
        "frequency": 604800,
        "tenant_id": "4feff6df-7454-4036-923d-7b2444462416",
        "chunk_size": 2,
        "intake_key": "0123456789",
    }

    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()
    return trigger


@pytest.fixture
def alert_query_2():
    return {
        "request_data": {
            "filters": [{"field": "server_creation_time", "operator": "gte", "value": 1706003700}],
            "search_from": 0,
            "search_to": 2,
            "sort": {"field": "creation_time", "keyword": "desc"},
        }
    }


@pytest.fixture
def alert_query_4():
    return {
        "request_data": {
            "filters": [{"field": "server_creation_time", "operator": "gte", "value": 1706003700}],
            "search_from": 2,
            "search_to": 4,
            "sort": {"field": "creation_time", "keyword": "desc"},
        }
    }


@pytest.fixture
def alert_response_2():
    return {
        "reply": {
            "total_count": 2,
            "result_count": 2,
            "alerts": [
                {
                    "external_id": "5e60680403934d",
                    "severity": "medium",
                    "events": [
                        {
                            "agent_install_type": "STANDARD",
                            "agent_host_boot_time": None,
                            "event_sub_type": None,
                        }
                    ],
                    "alert_id": "5930923",
                    "detection_timestamp": 1705912900118,
                },
                {
                    "external_id": "7317728957437371548",
                    "severity": "medium",
                    "events": [
                        {
                            "agent_install_type": "STANDARD",
                            "agent_host_boot_time": None,
                            "event_sub_type": None,
                            "image_name": None,
                        }
                    ],
                    "alert_id": "1",
                    "detection_timestamp": 1705912686000,
                },
            ],
        }
    }


@pytest.fixture
def alert_response_3_2():
    return {
        "reply": {
            "total_count": 3,
            "result_count": 2,
            "alerts": [
                {
                    "external_id": "5e60680403934d",
                    "severity": "medium",
                    "events": [
                        {
                            "agent_install_type": "STANDARD",
                            "agent_host_boot_time": None,
                            "event_sub_type": None,
                        }
                    ],
                    "alert_id": "5930923",
                    "detection_timestamp": 1705912900118,
                },
                {
                    "external_id": "7317728957437371548",
                    "severity": "medium",
                    "events": [
                        {
                            "agent_install_type": "STANDARD",
                            "agent_host_boot_time": None,
                            "event_sub_type": None,
                            "image_name": None,
                        }
                    ],
                    "alert_id": "1",
                    "detection_timestamp": 1705912686000,
                },
            ],
        }
    }


@pytest.fixture
def alert_response_3_1():
    return {
        "reply": {
            "total_count": 3,
            "result_count": 1,
            "alerts": [
                {
                    "external_id": "7317728957437371548",
                    "severity": "medium",
                    "events": [
                        {
                            "agent_install_type": "STANDARD",
                            "agent_host_boot_time": None,
                            "event_sub_type": None,
                            "image_name": None,
                        }
                    ],
                    "alert_id": "2",
                    "detection_timestamp": 1705912200,
                },
            ],
        }
    }


@pytest.fixture
def alert_response_4():
    return {
        "reply": {
            "total_count": 3,
            "result_count": 1,
            "alerts": [
                {
                    "external_id": "7317728957437371548",
                    "severity": "medium",
                    "events": [
                        {
                            "agent_install_type": "STANDARD",
                            "agent_host_boot_time": None,
                            "event_sub_type": None,
                            "image_name": None,
                        },
                        {"agent_install_type": "STANDARD", "agent_host_boot_time": None, "event_sub_type": "process"},
                    ],
                    "alert_id": "2",
                    "detection_timestamp": 1705912200,
                },
            ],
        }
    }


@pytest.fixture
def alert_response_0():
    return {"reply": {"total_count": 0, "result_count": 0, "alerts": []}}


@pytest.fixture
def alert_response_empty():
    return {"reply": {"total_count": 0, "result_count": 0, "alerts": None}}


def test_handle_fqdn():
    assert (
        handle_fqdn("https://api-XXXX.test.paloaltonetworks.com")
        == "https://api-XXXX.test.paloaltonetworks.com/public_api/v1/alerts/get_alerts_multi_events"
    )
    assert (
        handle_fqdn("api-XXXX.test.paloaltonetworks.com")
        == "https://api-XXXX.test.paloaltonetworks.com/public_api/v1/alerts/get_alerts_multi_events"
    )
    assert (
        handle_fqdn("XXXX.test.paloaltonetworks.com")
        == "https://api-XXXX.test.paloaltonetworks.com/public_api/v1/alerts/get_alerts_multi_events"
    )
    assert (
        handle_fqdn("https://XXXX.test.paloaltonetworks.com/public_api/v1/alerts/get_alerts_multi_events")
        == "https://XXXX.test.paloaltonetworks.com/public_api/v1/alerts/get_alerts_multi_events"
    )


@freeze_time("2024-01-23 10:00:00")
def test_getting_data_2(trigger, alert_response_2, alert_query_2):
    fqdn = trigger.module.configuration.fqdn
    alert_url = f"https://api-{fqdn}/public_api/v1/alerts/get_alerts_multi_events"

    with requests_mock.Mocker() as mock:
        mock.post(
            alert_url,
            status_code=200,
            json=alert_response_2,
            additional_matcher=lambda request: request.json() == alert_query_2,
        )

        trigger.get_all_alerts(2)
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        alerts_list = [orjson.loads(data) for data in calls[0]]
        assert len(alerts_list) == 2

        count_alerts = 0
        count_events = 0
        for data in alerts_list:
            if data.get("severity"):
                count_alerts += 1
            if data.get("agent_install_type"):
                count_events += 1

        assert count_alerts == 2
        assert count_events == 0


@freeze_time("2024-01-23 10:00:00")
def test_getting_data_3(trigger, alert_response_3_2, alert_response_3_1, alert_query_2, alert_query_4):
    fqdn = trigger.module.configuration.fqdn
    alert_url = f"https://api-{fqdn}/public_api/v1/alerts/get_alerts_multi_events"

    with requests_mock.Mocker() as mock:
        mock.post(
            alert_url,
            status_code=200,
            json=alert_response_3_2,
            additional_matcher=lambda request: request.json() == alert_query_2,
        )

        mock.post(
            alert_url,
            status_code=200,
            json=alert_response_3_1,
            additional_matcher=lambda request: request.json() == alert_query_4,
        )

        trigger.get_all_alerts(2)
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        first_alerts_batch = [orjson.loads(data) for data in calls[0]]
        second_alerts_batch = [orjson.loads(data) for data in calls[1]]
        assert len(first_alerts_batch) == 2
        assert len(second_alerts_batch) == 1

        count_alerts = 0
        count_events = 0
        first_alerts_batch.extend(second_alerts_batch)
        all_alerts = first_alerts_batch
        for data in all_alerts:
            if data.get("severity"):
                count_alerts += 1
            if data.get("agent_install_type"):
                count_events += 1

        assert count_alerts == 3
        assert count_events == 0


@freeze_time("2024-01-23 10:00:00")
def test_getting_data_0(trigger, alert_response_0, alert_query_2):
    fqdn = trigger.module.configuration.fqdn
    alert_url = f"https://api-{fqdn}/public_api/v1/alerts/get_alerts_multi_events"

    with requests_mock.Mocker() as mock:
        mock.post(
            alert_url,
            status_code=200,
            json=alert_response_0,
            additional_matcher=lambda request: request.json() == alert_query_2,
        )

        assert trigger.get_alerts_events_by_offset(0, trigger.timestamp_cursor, 2) == (0, [])


@freeze_time("2024-01-23 10:00:00")
def test_getting_data_0(trigger, alert_response_empty, alert_query_2):
    fqdn = trigger.module.configuration.fqdn
    alert_url = f"https://api-{fqdn}/public_api/v1/alerts/get_alerts_multi_events"

    with requests_mock.Mocker() as mock:
        mock.post(
            alert_url,
            status_code=200,
            json=alert_response_empty,
            additional_matcher=lambda request: request.json() == alert_query_2,
        )

        assert trigger.get_alerts_events_by_offset(0, trigger.timestamp_cursor, 2) == (0, [])


@freeze_time("2024-01-23 10:00:00")
def test_getting_data_400_http_code(trigger, alert_query_2):
    fqdn = trigger.module.configuration.fqdn
    alert_url = f"https://api-{fqdn}/public_api/v1/alerts/get_alerts_multi_events"

    with patch("cortex_module.cortex_edr_connector.time") as mock_time, requests_mock.Mocker() as mock:
        mock.post(
            alert_url,
            status_code=400,
        )

        trigger.forward_next_batch()
        assert trigger.log_exception.called


@freeze_time("2024-01-23 10:00:00")
def test_getting_data_with_authentication_failure(trigger, alert_query_2):
    fqdn = trigger.module.configuration.fqdn
    alert_url = f"https://api-{fqdn}/public_api/v1/alerts/get_alerts_multi_events"

    with patch("cortex_module.cortex_edr_connector.time") as mock_time, requests_mock.Mocker() as mock:
        mock.post(
            alert_url,
            status_code=401,
        )

        trigger.forward_next_batch()
        assert trigger.log.mock_calls == [
            call(level="critical", message="Authentication failed: Credentials are invalid")
        ]


@freeze_time("2024-01-23 10:00:00")
def test_getting_data_with_permission_failure(trigger, alert_query_2):
    fqdn = trigger.module.configuration.fqdn
    alert_url = f"https://api-{fqdn}/public_api/v1/alerts/get_alerts_multi_events"

    with patch("cortex_module.cortex_edr_connector.time") as mock_time, requests_mock.Mocker() as mock:
        mock.post(
            alert_url,
            status_code=403,
        )

        trigger.forward_next_batch()
        assert trigger.log.mock_calls == [
            call(level="critical", message="Permission denied: The operation isn't allowed for these credentials")
        ]


def test_splitting_events(trigger, alert_response_4):
    # first event should stay with alert, others should split into separate events
    result = trigger.split_alerts_events(alerts=alert_response_4["reply"]["alerts"])

    assert result == [
        '{"external_id":"7317728957437371548","severity":"medium","events":[{"agent_install_type":"STANDARD",'
        '"agent_host_boot_time":null,"event_sub_type":null,"image_name":null}],"alert_id":"2",'
        '"detection_timestamp":1705912200}',
        '{"agent_install_type":"STANDARD","agent_host_boot_time":null,"event_sub_type":"process","alert_id":"2"}',
    ]


@freeze_time("2024-01-23 10:00:00")
def test_external_id_cache_prevents_duplicates(trigger, alert_response_2, alert_query_2):
    """
    First call with these two alerts should return them.
    A second call with the same external_ids should yield (0, []).
    """
    fqdn = trigger.module.configuration.fqdn
    alert_url = f"https://api-{fqdn}/public_api/v1/alerts/get_alerts_multi_events"

    with requests_mock.Mocker() as mock:
        # Always return the same two-alert response
        mock.post(
            alert_url,
            status_code=200,
            json=alert_response_2,
            additional_matcher=lambda req: req.json() == alert_query_2,
        )

        # First fetch: we expect 2 alerts back
        total1, events1 = trigger.get_alerts_events_by_offset(0, trigger.timestamp_cursor, 2)
        assert total1 == 2
        assert isinstance(events1, list) and len(events1) == 2

        # Second fetch with the same batch: should be filtered out by the cache
        total2, events2 = trigger.get_alerts_events_by_offset(0, trigger.timestamp_cursor, 2)
        assert total2 == 0
        assert events2 == []
