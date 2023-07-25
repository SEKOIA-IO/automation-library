import time
from unittest.mock import Mock, MagicMock, patch

import pytest
import requests_mock

from vadecloud_modules import VadeCloudModule
from vadecloud_modules.trigger_vade_cloud_logs import (
    VadeCloudLogsConnector,
    VadeCloudConsumer,
)


@pytest.fixture
def trigger(symphony_storage):
    module = VadeCloudModule()
    trigger = VadeCloudLogsConnector(module=module, data_path=symphony_storage)

    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "login": "demo_1@demovade.com",
        "password": "pass",
        "hostname": "https://cloud-preview.vadesecure.com",
    }
    trigger.configuration = {
        "intake_key": "intake_key",
    }

    trigger.send_event = MagicMock()
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()

    return trigger


def test_fetch_event(trigger: VadeCloudLogsConnector):
    auth_message = {
        "accounts": [
            {
                "accountId": 2882,
                "accountState": "VALID",
                "accountType": "USER",
                "accountLogin": "VSC002984",
                "accountEmail": "demo_1@demovade.com",
                "oemId": 2,
                "oemLogin": "OEM0002",
                "accountDefaultLanguage": {
                    "id": 2,
                    "label": "French",
                    "nativeLabel": "Français",
                    "isoCode": "fr_FR",
                    "dateAndTimeFormat": "dd/MM/yyyy HH:mm",
                    "dateFormat": "dd/MM/yyyy",
                    "timeFormat": "HH:mm",
                    "onlyForQuarantine": False,
                },
                "accountFirstName": "Vade",
                "accountLastName": "Demo",
                "timezone": "Europe/Paris",
                "commercialUrl": "https://www.vadesecure.com/en/company/contact",
                "commercialLabel": "Service Commercial",
                "supportUrl": "https://www.vadesecure.com/en/support/",
                "supportLabel": "Support Technique",
                "brandUrl": "http://www.vadesecure.com",
                "brandLabel": "Demo partner",
                "onlineHelp": "",
            }
        ],
        "result": "OK",
    }

    response_message = {
        "logs": [
            {
                "message": '2023-07-20T09:15:02+00:00 localhost ulog[568]: [0000F4E4] qid=aaa1bbb2cc3,ip=1.2.3.4,sender=test@test.com,site=VSC000001,domain=maildomain.com,recipient=demo_1@maildomain.com: action=drop,status=virus,spamlevel=unknwon,tag=[VIRUS],stop=nil,reply=2,subject="Some subject"',
                "site": "VSC000001",
                "from": "test@test.com",
                "to": "demo_1@maildomain.com",
                "subject": "Some subject",
                "date": 1689844502000,
                "operationType": "DROP",
                "messageType": "VIRUS",
                "messageId": "aaa1bbb2cc3",
                "hostname": "localhost",
                "filterType": "UNKNOWN",
                "filterReason": "2",
                "spamLevel": "UNKNWON",
                "domain": "maildomain.com",
                "ip": "1.2.3.4",
                "tag": "[VIRUS]",
            }
        ]
    }

    with requests_mock.Mocker() as mock_requests, patch(
        "vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.get_last_timestamp",
        return_value=0,
    ) as mock_get_ts, patch(
        "vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.set_last_timestamp"
    ) as mock_set_ts, patch(
        "vadecloud_modules.trigger_vade_cloud_logs.time"
    ) as mock_time:
        mock_requests.post(
            "https://cloud-preview.vadesecure.com/rest/v3.0/login/login",
            status_code=200,
            json=auth_message,
        )
        mock_requests.post(
            "https://cloud-preview.vadesecure.com/rest/v3.0/filteringlog/getReport",
            [
                {"status_code": 200, "json": response_message},
                {"status_code": 200, "json": {"logs": []}},
            ],
        )

        consumer = VadeCloudConsumer(connector=trigger, name="inbound", params={"stream": "Inbound"})
        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1


def test_start_consumers(trigger):
    with patch("vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.start") as mock_start:
        consumers = trigger.start_consumers()

        assert "inbound" in consumers
        assert "outbound" in consumers
        assert mock_start.called


def test_supervise_consumers(trigger):
    with patch("vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.start") as mock_start:
        consumers = {
            "param_set_1": Mock(**{"is_alive.return_value": False, "running": True}),
            "param_set_2": None,
            "param_set_3": Mock(**{"is_alive.return_value": True, "running": True}),
            "param_set_4": Mock(**{"is_alive.return_value": False, "running": False}),
        }

        trigger.supervise_consumers(consumers)
        assert mock_start.call_count == 2


def test_stop_consumers(trigger):
    with patch("vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.start") as mock_start:
        consumers = {
            "param_set_1": Mock(**{"is_alive.return_value": False}),
            "param_set_2": None,
            "param_set_3": Mock(**{"is_alive.return_value": False}),
            "param_set_4": Mock(**{"is_alive.return_value": True}),
        }

        trigger.stop_consumers(consumers)

        offline_consumer = consumers.get("param_set_4")
        assert offline_consumer is not None
        assert offline_consumer.stop.called


def test_last_timestamp(trigger: VadeCloudLogsConnector):
    consumer = VadeCloudConsumer(connector=trigger, name="test", params={})

    now = int(time.time() * 1000)  # in milliseconds
    ts = now - 10_000

    consumer.set_last_timestamp(last_timestamp=ts)

    result = consumer.get_last_timestamp()

    assert result == ts
