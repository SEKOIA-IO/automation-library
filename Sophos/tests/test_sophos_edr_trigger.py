import os
from unittest.mock import Mock

import pytest
import requests_mock

from sophos_module.base import SophosModule
from sophos_module.trigger_sophos_edr_events import SophosEDREventsTrigger


@pytest.fixture
def trigger(symphony_storage):
    module = SophosModule()
    trigger = SophosEDREventsTrigger(module=module, data_path=symphony_storage)
    trigger.module.configuration = {
        "oauth2_authorization_url": "https://id.sophos.com/api/v2/oauth2/token",
        "api_host": "https://api-eu.central.sophos.com",
        "client_id": "my-id",
        "client_secret": "my-password",
    }
    trigger.configuration = {
        "frequency": 604800,
        "tenant_id": "9e3e9744-55c8-45f8-b5ca-e7076e06e1cf",
        "chunk_size": 1,
        "intake_key": "0123456789",
    }
    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()
    return trigger


def test_fetch_next_events(trigger):
    host = "https://api-eu02.central.sophos.com"
    url = f"{host}/siem/v1/events"

    with requests_mock.Mocker() as mock:
        mock.post(
            f"{trigger.module.configuration.oauth2_authorization_url}",
            status_code=200,
            json={
                "access_token": "access_token",
                "refresh_token": "refresh_token",
                "token_type": "bearer",
                "message": "OK",
                "errorCode": "success",
                "expires_in": 3600,
            },
        )

        mock.get(
            f"{trigger.module.configuration.api_host}/whoami/v1",
            status_code=200,
            json={
                "id": "ea106f70-96b1-4851-bd31-e4395ea407d2",
                "idType": "tenant",
                "apiHosts": {
                    "global": "https://api.central.sophos.com",
                    "dataRegion": host,
                },
            },
        )

        # flake8: noqa
        response = {
            "has_more": False,
            "next_cursor": "VjJfQ1VSU09SfDIwMTktMDQtMDFUMTg6MjU6NDEuNjA2Wg==",
            "items": [
                {
                    "when": "2019-04-01T15:11:09.759Z",
                    "id": "cbaff14f-a36b-46bd-8e83-6017ad79cdef",
                    "customer_id": "816f36ee-dd2e-4ccd-bb12-cea766c28ade",
                    "severity": "low",
                    "created_at": "2019-04-01T15:11:09.984Z",
                    "source_info": {"ip": "10.1.39.32"},
                    "endpoint_type": "server",
                    "endpoint_id": "c80c2a87-42f2-49b2-bab7-5031b69cd83e",
                    "origin": None,
                    "type": "Event::Endpoint::Registered",
                    "location": "mock_Mercury_1",
                    "source": "n/a",
                    "group": "PROTECTION",
                    "name": "New server registered: mock_Mercury_1",
                },
                {
                    "when": "2019-04-01T15:11:41.000Z",
                    "id": "5bc48f19-3905-4f72-9f79-cd381c8e92ce",
                    "customer_id": "816f36ee-dd2e-4ccd-bb12-cea766c28ade",
                    "severity": "medium",
                    "created_at": "2019-04-01T15:11:41.053Z",
                    "source_info": {"ip": "10.1.39.32"},
                    "endpoint_type": "server",
                    "endpoint_id": "c80c2a87-42f2-49b2-bab7-5031b69cd83e",
                    "origin": None,
                    "type": "Event::Endpoint::Threat::Detected",
                    "location": "mock_Mercury_1",
                    "source": "n/a",
                    "group": "MALWARE",
                    "name": "Malware detected: 'Eicar-AV-Test' at 'C:\\Program Files (x86)\\Trojan Horse\\bin\\eicar.com'",
                },
            ],
        }
        # flake8: qa
        mock.get(url, json=response)
        trigger.forward_next_batches()
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls) > 0


@pytest.mark.skipif("{'SOPHOS_CLIENT_ID', 'SOPHOS_CLIENT_SECRET'}.issubset(os.environ.keys()) == False")
def test_forward_next_batches_integration(symphony_storage):
    module = SophosModule()
    trigger = SophosEDREventsTrigger(module=module, data_path=symphony_storage)
    trigger.module.configuration = {
        "oauth2_authorization_url": os.environ.get("SOPHOS_AUTH_URL", "https://id.sophos.com/api/v2/oauth2/token"),
        "api_host": os.environ.get("SOPHOS_URL", "https://api-eu.central.sophos.com"),
        "client_id": os.environ["SOPHOS_CLIENT_ID"],
        "client_secret": os.environ["SOPHOS_CLIENT_SECRET"],
    }
    trigger.configuration = {"frequency": 0, "intake_key": "0123456789"}
    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()
    trigger.forward_next_batches()
    calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
    assert len(calls) > 0
