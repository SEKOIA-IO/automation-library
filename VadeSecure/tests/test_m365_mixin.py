from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch, call

import pytest
import requests_mock

from vadesecure_modules import VadeSecureModule
from vadesecure_modules.connector_m365_events import M365EventsConnector
from vadesecure_modules.m365_mixin import EventType, APIException


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


def test_fetch_events_with_authentication_error(trigger):
    trigger.module.configuration.api_host = "https://api-test.vadesecure.com/////"
    trigger.client.auth.get_authorization = MagicMock(return_value="Bearer 123456")
    with requests_mock.Mocker() as mock, patch("vadesecure_modules.connector_m365_events.time.sleep"):
        mock.post(
            "https://api-test.vadesecure.com/api/v1/tenants/e49e7162-0df6-48e9-a75e-237d54871e8b/logs/emails/search",
            status_code=401,
        )
        with pytest.raises(APIException):
            trigger._fetch_next_events(
                last_message_id="1", last_message_date=datetime.utcnow(), event_type=EventType.EMAILS
            )


def test_fetch_events_with_internal_server_error(trigger):
    trigger.module.configuration.api_host = "https://api-test.vadesecure.com/////"
    trigger.client.auth.get_authorization = MagicMock(return_value="Bearer 123456")
    with requests_mock.Mocker() as mock, patch("vadesecure_modules.connector_m365_events.time.sleep"):
        mock.post(
            "https://api-test.vadesecure.com/api/v1/tenants/e49e7162-0df6-48e9-a75e-237d54871e8b/logs/emails/search",
            status_code=500,
        )
        with pytest.raises(APIException):
            trigger._fetch_next_events(
                last_message_id="1", last_message_date=datetime.utcnow(), event_type=EventType.EMAILS
            )


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
                "content",
            ),
            "Unexpected API error 429 - Too many request - content",
        ),
    ],
)
def test_handle_api_exception(trigger: M365EventsConnector, error, expected_message):
    with requests_mock.Mocker() as mock, patch("vadesecure_modules.connector_m365_events.time.sleep"):
        trigger.client.auth.get_authorization = MagicMock(return_value="Bearer 123456")

        trigger.handle_api_exception(error)
        call(
            level="error",
            message=expected_message,
        ) in trigger.log.mock_calls
