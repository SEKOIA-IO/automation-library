from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests_mock
from faker import Faker

from vadesecure_modules import VadeSecureModule
from vadesecure_modules.connector_m365_events import M365EventsConnector
from vadesecure_modules.m365_mixin import EventType


@pytest.fixture
def trigger(symphony_storage):
    module = VadeSecureModule()
    trigger = M365EventsConnector(module=module, data_path=symphony_storage)

    trigger.module.configuration = {
        "oauth2_authorization_url": "https://api-test.vadesecure.com/oauth2/v2/token",
        "api_host": "https://api.vadesecure.com",
        "client_id": "my-id",
        "client_secret": "my-password",
    }
    trigger.configuration = {
        "frequency": 604800,
        "tenant_id": "e49e7162-0df6-48e9-a75e-237d54871e8b",
        "chunk_size": 1,
        "intake_key": "INTAKE_KEY",
    }
    trigger.push_events_to_intakes = MagicMock()
    trigger.log = Mock()
    trigger.log_exception = Mock()

    return trigger


def test_trigger_get_event_type_context(trigger: M365EventsConnector, session_faker: Faker):
    """
    Test `get_event_type_context`.

    Args:
        trigger: M365EventsConnector
        session_faker: Faker
    """
    random_key = [value for value in EventType][session_faker.pyint(0, len(EventType) - 1)]
    test_message_id = session_faker.pystr()
    with trigger.context as cache:
        cache[random_key.value] = None

    current_date = datetime.utcnow()
    one_hour_ago = current_date - timedelta(hours=1)

    result1 = trigger.get_event_type_context(random_key)

    assert (result1[0].replace(microsecond=0), result1[1]) == (one_hour_ago.replace(microsecond=0), None)

    with trigger.context as cache:
        cache[random_key.value] = {
            "last_message_date": current_date.isoformat(),
            "last_message_id": test_message_id,
        }

    assert trigger.get_event_type_context(random_key) == (current_date, test_message_id)


def test_fetch_events(trigger):
    trigger.client.auth.get_authorization = MagicMock(return_value="Bearer 123456")
    trigger._fetch_next_events = MagicMock(return_value=[])

    with patch("vadesecure_modules.connector_m365_events.time.sleep"):
        trigger._fetch_events()

    assert trigger.push_events_to_intakes.call_args_list == []
    assert len(trigger._fetch_next_events.call_args_list) == len(EventType)


def test_fetch_events_bad_url(trigger):
    trigger.module.configuration.api_host = "https://api-test.vadesecure.com/////"
    trigger.client.auth.get_authorization = MagicMock(return_value="Bearer 123456")
    with requests_mock.Mocker() as mock:
        mock.post(
            "https://api-test.vadesecure.com/api/v1/tenants/e49e7162-0df6-48e9-a75e-237d54871e8b/logs/emails/search",
            json={"result": {"total": 2, "messages": [{}, {}]}},
        )
        trigger._fetch_next_events(
            last_message_id="1", last_message_date=datetime.utcnow(), event_type=EventType.EMAILS
        )
        assert mock.called_once


def test_fetch_next_emails_events(trigger):
    url = (
        f"{trigger.module.configuration.api_host}/api/v1/tenants/"
        f"{trigger.configuration.tenant_id}/logs/emails/search"
    )

    with requests_mock.Mocker() as mock:
        trigger.client.auth.get_authorization = MagicMock(return_value="Bearer 123456")

        message1 = {
            "id": "c70589clfoov78sdpoa0",
            "date": "2021-12-20T10:00:05.966Z",
            "sender_ip": "163.172.240.104",
            "from": "nicole@sekoia.com",
            "from_header": '<nicole@sekoia.com>, "nikole@sekoia.com" <nikole@sekoia.com>',
            "to": "adrien@inthreat.com",
            "to_header": '"adrien@inthreat.com" <adrien@inthreat.com>',
            "subject": "2020 will hold no more secrets for you? - VadeSecure",
            "message_id": "<5f61e11a-6f15-467e-a531-efc455d26760@PR2FRA01FT001.eop-fra01.prod.protection.outlook.com>",
            "urls": [{"url": "https://inthreat.com/"}],
            "attachments": [
                {
                    "id": "c70589clfoov78sdpoag",
                    "filename": "",
                    "extension": "",
                    "size": 10558,
                },
                {
                    "id": "c70589clfoov78sdpob0",
                    "filename": "",
                    "extension": "",
                    "size": 12894,
                },
            ],
            "status": "HIGH_SPAM",
            "substatus": "",
            "remediation_type": "none",
            "remediation_ids": [],
            "action": "DELETE",
            "folder": "JunkEmail",
            "size": 155281,
            "current_events": [],
            "whitelisted": False,
        }
        message2 = {
            "id": "c70589d8h3e3tiops7hg",
            "date": "2021-12-20T10:00:05.793Z",
            "sender_ip": "163.172.240.104",
            "from": "flyforfree@sekoia.io",
            "from_header": "<flyforfree@sekoia.io>",
            "to": "legit@google.fr",
            "to_header": '"legit@google.fr" <legit@google.fr>',
            "subject": "Exclusive deal : 50% of your next vacations",
            "message_id": "<6cccc416-10e4-4977-bfb9-4aa09cfd2013@PR2FRA01FT011.eop-fra01.prod.protection.outlook.com>",
            "urls": [
                {"url": "https://getaway.xyz/fly-for-free"},
                {"url": "https://my-free-oil.us/new-law-for-free-gas.html"},
            ],
            "attachments": [],
            "status": "LEGIT",
            "substatus": "",
            "remediation_type": "none",
            "remediation_ids": [],
            "action": "NOTHING",
            "folder": "",
            "size": 112827,
            "current_events": [],
            "whitelisted": False,
        }
        mock.post(url, json={"result": {"total": 2, "messages": [message1, message2]}})
        assert trigger._fetch_next_events(
            last_message_id="", last_message_date=datetime.utcnow(), event_type=EventType.EMAILS
        ) == [message1, message2]


def test_fetch_next_auto_remediation_events(trigger):
    url = (
        f"{trigger.module.configuration.api_host}/api/v1/tenants/"
        f"{trigger.configuration.tenant_id}/logs/remediations/auto/search"
    )

    with requests_mock.Mocker() as mock:
        trigger.client.auth.get_authorization = MagicMock(return_value="Bearer 123456")

        campaign1 = {
            "action": ["DELETE"],
            "date": "2021-12-20T10:00:06.891Z",
            "id": "d855zdg64sd45e123456",
            "nb_messages_remediated": 3,
            "nb_messages_remediated_read": 2,
            "nb_messages_remediated_unread": 1,
            "reason": "An wonderful explanation",
            "status": {"status": "HIGH_SPAM", "substatus": "LAWYER_FRAUD"},
        }

        mock.post(url, json={"result": {"total": 2, "campaigns": [campaign1]}})
        assert trigger._fetch_next_events(
            last_message_id="",
            last_message_date=datetime.utcnow(),
            event_type=EventType.REMEDIATIONS_AUTO,
        ) == [campaign1]


def test_get_authorization_request_new_token_only_when_needed(trigger):
    url = trigger.module.configuration.oauth2_authorization_url

    with requests_mock.Mocker() as mock:
        mock.post(
            url,
            json={
                "access_token": "123456",
                "expires_in": 10,
                "scope": "our-scope",
                "token_type": "bearer",
            },
        )

        token = trigger.client.auth.get_authorization()
        assert token == "Bearer 123456"

        mock.post(
            url,
            json={
                "access_token": "78910",
                "expires_in": 10000,
                "scope": "our-scope",
                "token_type": "bearer",
            },
        )
        token = trigger.client.auth.get_authorization()
        assert token == "Bearer 78910"

        mock.post(
            url,
            json={
                "access_token": "11111",
                "expires_in": 10000,
                "scope": "our-scope",
                "token_type": "bearer",
            },
        )

        token = trigger.client.auth.get_authorization()
        assert token == "Bearer 78910"

        assert mock.call_count == 2
