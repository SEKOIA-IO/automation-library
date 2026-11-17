import time
from typing import Any
from unittest.mock import MagicMock, Mock, call, patch

import pytest
import requests.exceptions
import requests_mock

from vadecloud_modules import VadeCloudModule
from vadecloud_modules.trigger_vade_cloud_logs import (
    APIException,
    FetchEventException,
    VadeCloudConsumer,
    VadeCloudLogsConnector,
)


@pytest.fixture
def trigger(symphony_storage):
    module = VadeCloudModule()
    trigger = VadeCloudLogsConnector(module=module, data_path=symphony_storage)

    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "login": "john.doe@example.com",
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


@pytest.fixture
def auth_message():
    return {
        "accounts": [
            {
                "accountId": 1001,
                "accountState": "VALID",
                "accountType": "USER",
                "accountLogin": "VSC000000",
                "accountEmail": "john.doe@example.com",
                "oemId": 2,
                "oemLogin": "OEM0000",
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
                "accountFirstName": "John",
                "accountLastName": "Doe",
                "timezone": "Europe/Paris",
                "commercialUrl": "https://www.vadesecure.com/en/company/contact",
                "commercialLabel": "Service Commercial",
                "supportUrl": "https://www.vadesecure.com/en/support/",
                "supportLabel": "Support Technique",
                "brandUrl": "http://www.vadesecure.com",
                "brandLabel": "Example partner",
                "onlineHelp": "",
            }
        ],
        "result": "OK",
    }


@pytest.fixture
def auth_message_admin():
    return {
        "accounts": [
            {
                "accountId": 1002,
                "accountState": "VALID",
                "accountType": "ADMINISTRATOR",
                "accountLogin": "VSC000000",
                "accountEmail": "john.doe@example.com",
                "userId": 2002,
                "oemId": 2,
                "oemLogin": "OEM0000",
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
                "accountFirstName": "John",
                "accountLastName": "Doe",
                "timezone": "Europe/Paris",
                "commercialUrl": "https://www.vadesecure.com/en/company/contact",
                "commercialLabel": "Service Commercial",
                "supportUrl": "https://www.vadesecure.com/en/support/",
                "supportLabel": "Support Technique",
                "brandUrl": "http://www.vadesecure.com",
                "brandLabel": "Example partner",
                "onlineHelp": "",
            }
        ],
        "result": "OK",
    }


@pytest.fixture
def auth_message_quarantine():
    return {
        "accounts": [
            {
                "accountId": 1003,
                "accountState": "VALID",
                "accountType": "QUARANTINE",
                "accountLogin": "VSC000000",
                "accountEmail": "john.doe@example.com",
                "userId": 2003,
                "oemId": 2,
                "oemLogin": "OEM0000",
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
                "accountFirstName": "John",
                "accountLastName": "Doe",
                "timezone": "Europe/Paris",
                "commercialUrl": "https://www.vadesecure.com/en/company/contact",
                "commercialLabel": "Service Commercial",
                "supportUrl": "https://www.vadesecure.com/en/support/",
                "supportLabel": "Support Technique",
                "brandUrl": "http://www.vadesecure.com",
                "brandLabel": "Example partner",
                "onlineHelp": "",
            }
        ],
        "result": "OK",
    }


@pytest.fixture
def response_message():
    return {
        "logs": [
            {
                "message": '2023-07-20T09:15:02+00:00 localhost ulog[568]: [0000F4E4] qid=aaa1bbb2cc3,ip=192.0.2.1,sender=sender@example.net,site=VSC000001,domain=example.org,recipient=jane.doe@example.org: action=drop,status=virus,spamlevel=unknwon,tag=[VIRUS],stop=nil,reply=2,subject="Some subject"',
                "site": "VSC000001",
                "from": "sender@example.net",
                "to": "jane.doe@example.org",
                "subject": "Some subject",
                "date": 1689844502000,
                "operationType": "DROP",
                "messageType": "VIRUS",
                "messageId": "aaa1bbb2cc3",
                "hostname": "localhost",
                "filterType": "UNKNOWN",
                "filterReason": "2",
                "spamLevel": "UNKNWON",
                "domain": "example.org",
                "ip": "192.0.2.1",
                "tag": "[VIRUS]",
            }
        ]
    }


def test_auth_error(trigger: VadeCloudLogsConnector):
    with (
        requests_mock.Mocker() as mock_requests,
        patch(
            "vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.get_last_timestamp",
            return_value=0,
        ) as mock_get_ts,
        patch("vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.set_last_timestamp") as mock_set_ts,
        patch("vadecloud_modules.trigger_vade_cloud_logs.time") as mock_time,
    ):
        mock_requests.post(
            "https://cloud-preview.vadesecure.com/rest/v3.0/login/login",
            status_code=404,
            json={"error": {"code": 404, "message": "Not found", "reason": "USER_UNKNOWN", "trKey": "USER_UNKNOWN"}},
        )

        with pytest.raises(requests.exceptions.HTTPError) as context:
            trigger.create_client()


def test_auth_user_invalid(trigger: VadeCloudLogsConnector):
    with (
        requests_mock.Mocker() as mock_requests,
        patch(
            "vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.get_last_timestamp",
            return_value=0,
        ) as _,
        patch("vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.set_last_timestamp") as _,
        patch("vadecloud_modules.trigger_vade_cloud_logs.time") as _,
    ):
        mock_requests.post(
            "https://cloud-preview.vadesecure.com/rest/v3.0/login/login",
            status_code=400,
            json={"error": {"code": 400, "message": "ID specified is not a user account", "trKey": "INVALID_USER"}},
        )

        with pytest.raises(requests.exceptions.HTTPError) as context:
            trigger.create_client()


def test_timeout_error(trigger: VadeCloudLogsConnector):
    with (
        requests_mock.Mocker() as mock_requests,
        patch(
            "vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.get_last_timestamp",
            return_value=0,
        ) as mock_get_ts,
        patch("vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.set_last_timestamp") as mock_set_ts,
        patch("vadecloud_modules.trigger_vade_cloud_logs.time") as mock_time,
    ):
        mock_requests.post(
            "https://cloud-preview.vadesecure.com/rest/v3.0/login/login",
            exc=requests.exceptions.Timeout,
        )

        with pytest.raises(TimeoutError):
            trigger.create_client()


def test_request_with_account_id_administrator(
    trigger: VadeCloudLogsConnector, auth_message_admin: list[dict[str, Any]]
) -> None:
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://cloud-preview.vadesecure.com/rest/v3.0/login/login",
            status_code=200,
            json=auth_message_admin,
        )
        api_client = trigger.create_client()

        consumer = VadeCloudConsumer(
            connector=trigger, name="inbound", client=api_client, params={"stream": "Inbound"}
        )

        assert consumer.client.account_id == 2002


def test_request_with_account_id_quarantine(
    trigger: VadeCloudLogsConnector, auth_message_quarantine: list[dict[str, Any]]
) -> None:
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://cloud-preview.vadesecure.com/rest/v3.0/login/login",
            status_code=200,
            json=auth_message_quarantine,
        )
        api_client = trigger.create_client()

        consumer = VadeCloudConsumer(
            connector=trigger, name="inbound", client=api_client, params={"stream": "Inbound"}
        )

        assert consumer.client.account_id == 2003


def test_request_error(trigger: VadeCloudLogsConnector, auth_message):
    with (
        requests_mock.Mocker() as mock_requests,
        patch(
            "vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.get_last_timestamp",
            return_value=0,
        ) as _,
        patch("vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.set_last_timestamp") as _,
        patch("vadecloud_modules.trigger_vade_cloud_logs.time") as _,
    ):
        mock_requests.post(
            "https://cloud-preview.vadesecure.com/rest/v3.0/login/login",
            status_code=200,
            json=auth_message,
        )
        mock_requests.post(
            "https://cloud-preview.vadesecure.com/rest/v3.0/filteringlog/getReport",
            [
                {
                    "status_code": 400,
                    "json": {
                        "result": "NOK",
                        "error": {"code": 400, "message": "Missing streamType", "trKey": "MISSING_STREAM_TYPE"},
                    },
                },
            ],
        )

        api_client = trigger.create_client()
        consumer = VadeCloudConsumer(
            connector=trigger, name="inbound", client=api_client, params={"stream": "Inbound"}
        )

        with pytest.raises(FetchEventException):
            consumer.next_batch()


def test_request_without_permission_stop_trigger(trigger: VadeCloudLogsConnector, auth_message):
    with (
        requests_mock.Mocker() as mock_requests,
        patch(
            "vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.get_last_timestamp",
            return_value=0,
        ) as _,
        patch("vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.set_last_timestamp") as _,
        patch("vadecloud_modules.trigger_vade_cloud_logs.time") as _,
    ):
        mock_requests.post(
            "https://cloud-preview.vadesecure.com/rest/v3.0/login/login",
            status_code=200,
            json=auth_message,
        )
        mock_requests.post(
            "https://cloud-preview.vadesecure.com/rest/v3.0/filteringlog/getReport",
            status_code=403,
            json={
                "result": "NOK",
                "error": {"code": 403, "message": "permission denied", "trKey": "PERMISSION_DENIED"},
            },
        )

        api_client = trigger.create_client()
        consumer = VadeCloudConsumer(
            connector=trigger, name="inbound", client=api_client, params={"stream": "Inbound"}
        )

        consumer.next_batch()
        call(
            level="critical",
            message="Request on Vade Cloud API to fetch `inbound` logs failed with status 403 - Forbidden",
        ) in trigger.log.mock_calls


def test_request_with_authentication_failure_raise_APIException(trigger: VadeCloudLogsConnector, auth_message):
    with (
        requests_mock.Mocker() as mock_requests,
        patch(
            "vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.get_last_timestamp",
            return_value=0,
        ) as _,
        patch("vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.set_last_timestamp") as _,
        patch("vadecloud_modules.trigger_vade_cloud_logs.time") as _,
    ):
        mock_requests.post(
            "https://cloud-preview.vadesecure.com/rest/v3.0/login/login",
            status_code=200,
            json=auth_message,
        )
        mock_requests.post(
            "https://cloud-preview.vadesecure.com/rest/v3.0/filteringlog/getReport",
            status_code=401,
            json={
                "result": "NOK",
                "error": {"code": 401, "message": "authentication failed", "trKey": "AUTH_FAILURE"},
            },
        )

        api_client = trigger.create_client()
        consumer = VadeCloudConsumer(
            connector=trigger, name="inbound", client=api_client, params={"stream": "Inbound"}
        )

        with pytest.raises(APIException):
            consumer.next_batch()


def test_request_with_server_error_raise_APIException(trigger: VadeCloudLogsConnector, auth_message):
    with (
        requests_mock.Mocker() as mock_requests,
        patch(
            "vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.get_last_timestamp",
            return_value=0,
        ) as _,
        patch("vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.set_last_timestamp") as _,
        patch("vadecloud_modules.trigger_vade_cloud_logs.time") as _,
    ):
        mock_requests.post(
            "https://cloud-preview.vadesecure.com/rest/v3.0/login/login",
            status_code=200,
            json=auth_message,
        )
        mock_requests.post(
            "https://cloud-preview.vadesecure.com/rest/v3.0/filteringlog/getReport",
            status_code=500,
            json={
                "result": "NOK",
                "error": {"code": 500, "message": "context deadline exceeded", "trKey": "INTERNAL_ERROR"},
            },
        )

        api_client = trigger.create_client()
        consumer = VadeCloudConsumer(
            connector=trigger, name="inbound", client=api_client, params={"stream": "Inbound"}
        )

        with pytest.raises(APIException):
            consumer.next_batch()


@pytest.mark.parametrize(
    "error,expected_message",
    [
        (
            APIException(401, "Unauthorized", "content"),
            "The VadeCloud API raised an authentication issue. Please check our credentials",
        ),
        (
            APIException(500, "Internal error", "context deadline exceeded"),
            "The VadeCloud API raised an internal error. Please contact the Vade support if the issue persist",
        ),
        (
            APIException(
                429,
                "Too many request",
                '{"result": "NOK", "error": {"code": 429, "message": "too many request", "trKey": "too_many_request"}}',
            ),
            'Unexpected API error 429 - Too many request - {"result": "NOK", "error": {"code": 429, "message": "too many request", "trKey": "too_many_request"}}',
        ),
    ],
)
def test_handle_api_exception(trigger: VadeCloudLogsConnector, auth_message, error, expected_message):
    with (
        requests_mock.Mocker() as mock_requests,
        patch(
            "vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.get_last_timestamp",
            return_value=0,
        ) as _,
        patch("vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.set_last_timestamp") as _,
        patch("vadecloud_modules.trigger_vade_cloud_logs.time") as _,
    ):
        mock_requests.post(
            "https://cloud-preview.vadesecure.com/rest/v3.0/login/login",
            status_code=200,
            json=auth_message,
        )

        api_client = trigger.create_client()
        consumer = VadeCloudConsumer(
            connector=trigger, name="inbound", client=api_client, params={"stream": "Inbound"}
        )
        consumer.handle_api_exception(error)
        call(
            level="error",
            message=expected_message,
        ) in trigger.log.mock_calls


def test_fetch_event(trigger: VadeCloudLogsConnector, auth_message, response_message):
    with (
        requests_mock.Mocker() as mock_requests,
        patch(
            "vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.get_last_timestamp",
            return_value=0,
        ) as mock_get_ts,
        patch("vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.set_last_timestamp") as mock_set_ts,
        patch("vadecloud_modules.trigger_vade_cloud_logs.time") as mock_time,
    ):
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

        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        api_client = trigger.create_client()
        consumer = VadeCloudConsumer(
            connector=trigger, name="inbound", client=api_client, params={"stream": "Inbound"}
        )
        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        mock_time.sleep.assert_called_once_with(44)


@pytest.fixture
def api_client(trigger, auth_message):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://cloud-preview.vadesecure.com/rest/v3.0/login/login",
            status_code=200,
            json=auth_message,
        )
        return trigger.create_client()


def test_start_consumers(trigger, api_client):
    with patch("vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.start") as mock_start:
        consumers = trigger.start_consumers(client=api_client)

        assert "inbound" in consumers
        assert "outbound" in consumers
        assert mock_start.called


def test_supervise_consumers(trigger, api_client):
    with patch("vadecloud_modules.trigger_vade_cloud_logs.VadeCloudConsumer.start") as mock_start:
        consumers = {
            "param_set_1": Mock(**{"is_alive.return_value": False, "running": True}),
            "param_set_2": None,
            "param_set_3": Mock(**{"is_alive.return_value": True, "running": True}),
            "param_set_4": Mock(**{"is_alive.return_value": False, "running": False}),
        }

        trigger.supervise_consumers(consumers, client=api_client)
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


def test_last_timestamp(trigger: VadeCloudLogsConnector, api_client):
    consumer = VadeCloudConsumer(connector=trigger, name="test", client=api_client, params={})

    now = int(time.time() * 1000)  # in milliseconds
    ts = now - 10_000

    consumer.set_last_timestamp(last_timestamp=ts)

    result = consumer.get_last_timestamp()

    assert result == ts


def test_last_timestamp_per_stream(trigger: VadeCloudLogsConnector, api_client):
    inbound = VadeCloudConsumer(connector=trigger, name="inbound", client=api_client, params={})
    outbound = VadeCloudConsumer(connector=trigger, name="outbound", client=api_client, params={})

    now = int(time.time() * 1000)
    inbound.set_last_timestamp(last_timestamp=now - 10_000)
    outbound.set_last_timestamp(last_timestamp=now - 20_000)
    inbound.set_last_timestamp(last_timestamp=now - 5_000)

    assert inbound.get_last_timestamp() == now - 5_000
    assert outbound.get_last_timestamp() == now - 20_000


def test_last_timestamp_migrates_shared_checkpoint(trigger: VadeCloudLogsConnector, api_client):
    inbound = VadeCloudConsumer(connector=trigger, name="inbound", client=api_client, params={})
    outbound = VadeCloudConsumer(connector=trigger, name="outbound", client=api_client, params={})

    legacy_ts = int(time.time() * 1000) - 10_000
    with trigger.context as cache:
        cache["last_ts"] = legacy_ts

    assert inbound.get_last_timestamp() == legacy_ts
    assert outbound.get_last_timestamp() == legacy_ts

    inbound.set_last_timestamp(last_timestamp=legacy_ts + 5_000)

    assert inbound.get_last_timestamp() == legacy_ts + 5_000
    assert outbound.get_last_timestamp() == legacy_ts


def test_last_timestamp_first_run(trigger: VadeCloudLogsConnector, api_client):
    consumer = VadeCloudConsumer(connector=trigger, name="inbound", client=api_client, params={})

    with patch("vadecloud_modules.trigger_vade_cloud_logs.time.time", return_value=1_700_000_000.0):
        assert consumer.get_last_timestamp() == 1_700_000_000_000 - 5 * 60 * 1000
