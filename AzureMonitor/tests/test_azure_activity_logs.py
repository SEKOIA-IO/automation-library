from unittest.mock import MagicMock, patch

import pytest

from azure_monitor_modules import AzureMonitorModule
from azure_monitor_modules.azure_activity_logs import AzureActivityLogsConnector


@pytest.fixture
def trigger(data_storage):
    module = AzureMonitorModule()
    module.configuration = {
        "client_id": "CLIENT_ID",
        "client_secret": "SECRET",
        "tenant_id": "00000000-0000-0000-0000-000000000000",
    }
    trigger = AzureActivityLogsConnector(module=module, data_path=data_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = {
        "subscription_id": "11111111-1111-1111-1111-111111111111",
        "intake_key": "intake_key",
    }
    yield trigger


@pytest.fixture
def message_1():
    # From https://learn.microsoft.com/en-us/rest/api/monitor/activity-logs/list
    return {
        "authorization": {
            "action": "microsoft.support/supporttickets/write",
            "role": "Subscription Admin",
            "scope": "/subscriptions/089bd33f-d4ec-47fe-8ba5-0753aa5c5b33/resourceGroups/MSSupportGroup/providers/microsoft.support/supporttickets/115012112305841",
        },
        "caller": "admin@contoso.com",
        "claims": {
            "aud": "https://management.core.windows.net/",
            "iss": "https://sts.windows.net/72f988bf-86f1-41af-91ab-2d7cd011db47/",
            "iat": "1421876371",
            "nbf": "1421876371",
            "exp": "1421880271",
            "ver": "1.0",
            "http://schemas.microsoft.com/identity/claims/tenantid": "1e8d8218-c5e7-4578-9acc-9abbd5d23315",
            "http://schemas.microsoft.com/claims/authnmethodsreferences": "pwd",
            "http://schemas.microsoft.com/identity/claims/objectidentifier": "2468adf0-8211-44e3-95xq-85137af64708",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn": "admin@contoso.com",
            "puid": "20030000801A118C",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier": "9vckmEGF7zDKk1YzIY8k0t1_EAPaXoeHyPRn6f413zM",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname": "John",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname": "Smith",
            "name": "John Smith",
            "groups": "cacfe77c-e058-4712-83qw-f9b08849fd60,7f71d11d-4c41-4b23-99d2-d32ce7aa621c,31522864-0578-4ea0-9gdc-e66cc564d18c",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name": "admin@contoso.com",
            "appid": "c44b4083-3bq0-49c1-b47d-974e53cbdf3c",
            "appidacr": "2",
            "http://schemas.microsoft.com/identity/claims/scope": "user_impersonation",
            "http://schemas.microsoft.com/claims/authnclassreference": "1",
        },
        "correlationId": "1e121103-0ba6-4300-ac9d-952bb5d0c80f",
        "description": "",
        "eventDataId": "44ade6b4-3813-45e6-ae27-7420a95fa2f8",
        "eventName": {"value": "EndRequest", "localizedValue": "End request"},
        "httpRequest": {
            "clientRequestId": "27003b25-91d3-418f-8eb1-29e537dcb249",
            "clientIpAddress": "192.168.35.115",
            "method": "PUT",
        },
        "id": "/subscriptions/089bd33f-d4ec-47fe-8ba5-0753aa5c5b33/resourceGroups/MSSupportGroup/providers/microsoft.support/supporttickets/115012112305841/events/44ade6b4-3813-45e6-ae27-7420a95fa2f8/ticks/635574752669792776",
        "level": "Informational",
        "resourceGroupName": "MSSupportGroup",
        "resourceProviderName": {"value": "microsoft.support", "localizedValue": "microsoft.support"},
        "operationId": "1e121103-0ba6-4300-ac9d-952bb5d0c80f",
        "operationName": {
            "value": "microsoft.support/supporttickets/write",
            "localizedValue": "microsoft.support/supporttickets/write",
        },
        "properties": {"statusCode": "Created"},
        "status": {"value": "Succeeded", "localizedValue": "Succeeded"},
        "subStatus": {"value": "Created", "localizedValue": "Created (HTTP Status Code: 201)"},
        "eventTimestamp": "2015-01-21T22:14:26.9792776Z",
        "submissionTimestamp": "2015-01-21T22:14:39.9936304Z",
        "subscriptionId": "089bd33f-d4ec-47fe-8ba5-0753aa5c5b33",
    }


def test_list_activity_logs_empty(trigger):
    client = trigger.client

    client.activity_logs.list = MagicMock()
    client.activity_logs.list.return_value = iter([])

    with patch("azure_monitor_modules.azure_activity_logs.time") as mock_time:
        trigger.next_batch()

    assert trigger.push_events_to_intakes.call_count == 0
    assert mock_time.sleep.call_count == 1


def test_list_activity_logs_with_message(trigger, message_1):
    client = trigger.client

    message_mock = MagicMock()
    message_mock.serialize.return_value = message_1

    client.activity_logs.list = MagicMock()
    client.activity_logs.list.return_value = iter([message_mock])

    with patch("azure_monitor_modules.azure_activity_logs.time") as mock_time:
        trigger.next_batch()

    assert trigger.push_events_to_intakes.call_count == 1
    assert mock_time.sleep.call_count == 1


def test_check_filters_configuration(trigger):
    # without any filter
    trigger.check_filters_configuration()

    # with 1 filter
    trigger.configuration.filter_resource = "SOME_RESOURCE"
    trigger.check_filters_configuration()

    # with 2 filters
    trigger.configuration.filter_resource_group = "SOME_RESOURCE_GROUP"
    with pytest.raises(ValueError):
        trigger.check_filters_configuration()
