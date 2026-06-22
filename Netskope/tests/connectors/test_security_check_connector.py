from unittest.mock import MagicMock, patch

import pytest
import requests_mock
from netskope_api.iterator.netskope_iterator import NetskopeIterator

from netskope_modules import NetskopeModule
from netskope_modules.connectors.connector_pull_events_v2 import NetskopeEventConnector, NetskopeEventConsumer
from netskope_modules.types import NetskopeAlertType, NetskopeEventType


def make_trigger(symphony_storage, security_check_only):
    module = NetskopeModule()
    module._trigger_configuration_uuid = "ec92e51c-d45e-47b1-b820-29b97721623f"
    trigger = NetskopeEventConnector(module=module, data_path=symphony_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "base_url": "https://my.fake.sekoia",
    }
    trigger.configuration = {
        "api_token": "api_token",
        "intake_key": "intake_key",
        "consumer_group": "",
        "security_check_only": security_check_only,
    }
    return trigger


@pytest.fixture
def trigger(symphony_storage):
    return make_trigger(symphony_storage, security_check_only=True)


def test_dataexports_only_contains_security_check_alerts(trigger):
    assert trigger.dataexports == [
        (NetskopeEventType.ALERT, NetskopeAlertType.MALWARE),
        (NetskopeEventType.ALERT, NetskopeAlertType.MALSITE),
        (NetskopeEventType.ALERT, NetskopeAlertType.DLP),
    ]


def test_dataexports_default_contains_full_list(symphony_storage):
    trigger = make_trigger(symphony_storage, security_check_only=False)

    assert len(trigger.dataexports) == 17
    assert (NetskopeEventType.PAGE, None) in trigger.dataexports
    assert (NetskopeEventType.ALERT, NetskopeAlertType.UBA) in trigger.dataexports


def test_create_iterators_covers_only_three_endpoints(trigger):
    iterators = trigger.create_iterators(trigger.dataexports)

    assert len(iterators) == 3
    assert set(iterators.keys()) == {"alert-malware", "alert-malsite", "alert-dlp"}
    for iterator in iterators.values():
        assert isinstance(iterator, NetskopeIterator)


@pytest.mark.parametrize(
    "alert_type,endpoint",
    [
        (NetskopeAlertType.MALWARE, "https://my.fake.sekoia/api/v2/events/dataexport/alerts/malware"),
        (NetskopeAlertType.MALSITE, "https://my.fake.sekoia/api/v2/events/dataexport/alerts/malsite"),
        (NetskopeAlertType.DLP, "https://my.fake.sekoia/api/v2/events/dataexport/alerts/dlp"),
    ],
)
def test_next_batch_pushes_events_for_each_alert_type(trigger, alert_type, endpoint):
    with (
        patch("netskope_modules.connectors.connector_pull_events_v2.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(
            endpoint,
            status_code=200,
            json={
                "ok": 1,
                "result": [
                    {
                        "timestamp": 1651424472,
                        "_id": "abc123",
                        "alert_type": alert_type.value,
                    }
                ],
            },
        )
        iterator = trigger.create_iterator(NetskopeEventType.ALERT, alert_type)
        consumer = NetskopeEventConsumer(trigger, f"alert-{alert_type.value}", iterator)
        start_time = 1666711174.0
        end_time = start_time + 5
        mock_time.time.side_effect = [start_time, end_time, end_time]

        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
