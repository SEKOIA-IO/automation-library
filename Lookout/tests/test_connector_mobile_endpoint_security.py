import json
from unittest.mock import MagicMock, patch

import pytest
import requests_mock

from lookout_modules import LookoutModule
from lookout_modules.connector_mobile_endpoint_security import (
    MobileEndpointSecurityConnector,
    MobileEndpointSecurityThread,
)


@pytest.fixture
def trigger(data_storage):
    module = LookoutModule()
    module.configuration = {
        "host": "https://api.lookout.com",
        "api_token": "API_TOKEN",
    }
    trigger = MobileEndpointSecurityConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = {
        "intake_key": "intake_key",
    }
    yield trigger


@pytest.fixture
def worker(trigger):
    yield MobileEndpointSecurityThread(connector=trigger)


@pytest.fixture
def sse_stream():
    data = json.dumps(
        [
            {
                "actor": {"type": "SYSTEM"},
                "audit": {"type": "ENTERPRISE"},
                "change_type": "PURGED",
                "created_time": "2025-05-05T00:41:43.499+00:00",
                "enterprise_guid": "82648f9f-5f97-4460-b317-2d1bb971d2d9",
                "id": "01969de4-3d58-7983-9a49-cff6ceddcf6a",
                "target": {"guid": "82648f9f-5f97-4460-b317-2d1bb971d2d9", "type": "ENTERPRISE"},
                "type": "AUDIT",
            },
            {
                "actor": {"type": "SYSTEM"},
                "audit": {"type": "ENTERPRISE"},
                "change_type": "PURGED",
                "created_time": "2025-05-05T04:42:11.327+00:00",
                "enterprise_guid": "82648f9f-5f97-4460-b317-2d1bb971d2d9",
                "id": "01969ec0-64b8-7aad-80dd-0bcebb5c99b2",
                "target": {"guid": "82648f9f-5f97-4460-b317-2d1bb971d2d9", "type": "ENTERPRISE"},
                "type": "AUDIT",
            },
            {
                "actor": {"type": "SYSTEM"},
                "audit": {"type": "ENTERPRISE"},
                "change_type": "PURGED",
                "created_time": "2025-05-05T07:54:29.488+00:00",
                "enterprise_guid": "82648f9f-5f97-4460-b317-2d1bb971d2d9",
                "id": "01969f70-7308-7f75-922a-527101520ba2",
                "target": {"guid": "82648f9f-5f97-4460-b317-2d1bb971d2d9", "type": "ENTERPRISE"},
                "type": "AUDIT",
            },
            {
                "actor": {"guid": "cdbf17c9-995c-4a31-80f2-67bd8e02a1a6", "type": "ADMIN"},
                "audit": {"attribute_changes": [{"name": "login"}], "type": "ADMIN_LOGIN"},
                "change_type": "CREATED",
                "created_time": "2025-05-05T08:16:14.538+00:00",
                "enterprise_guid": "82648f9f-5f97-4460-b317-2d1bb971d2d9",
                "id": "01969f84-5cb0-73a9-93a4-4d924d09f605",
                "target": {"guid": "82648f9f-5f97-4460-b317-2d1bb971d2d9", "type": "ENTERPRISE"},
                "type": "AUDIT",
            },
            {
                "actor": {"guid": "cdbf17c9-995c-4a31-80f2-67bd8e02a1a6", "type": "ADMIN"},
                "audit": {
                    "attribute_changes": [
                        {"name": "ent_application_key"},
                        {"name": "key_guid", "to": "7323f657-f90a-469d-b2d0-e2ba2cafafcf"},
                        {"name": "key_name", "to": "Integration test"},
                    ],
                    "type": "ENTERPRISE",
                },
                "change_type": "CREATED",
                "created_time": "2025-05-05T08:17:59.345+00:00",
                "enterprise_guid": "82648f9f-5f97-4460-b317-2d1bb971d2d9",
                "id": "01969f85-f6d8-73bd-bcbc-a38948f21386",
                "target": {"guid": "82648f9f-5f97-4460-b317-2d1bb971d2d9", "type": "ENTERPRISE"},
                "type": "AUDIT",
            },
        ]
    )
    return """event:heartbeat\ndata:{}\n\nid:01969f85-f6d8-73bd-bcbc-a38948f21386\nevent:events\ndata:%s\n\n""" % data


def test_fetch_events(worker, sse_stream):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.register_uri(
            "POST",
            f"https://api.lookout.com/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.register_uri(
            "GET",
            "https://api.lookout.com/mra/stream/v2/events",
            text=sse_stream,
        )

        events = list(worker.fetch_events())
        assert len(events) == 2


def test_reconnect(worker):
    with requests_mock.Mocker() as mock_requests, patch(
        "lookout_modules.connector_mobile_endpoint_security.time"
    ) as mock_time:
        mock_requests.register_uri(
            "POST",
            f"https://api.lookout.com/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.register_uri(
            "GET",
            "https://api.lookout.com/mra/stream/v2/events",
            text="""event:reconnect\nretry:1000\n\n""",
        )

        events = list(worker.fetch_events())
        assert len(events) == 0

        mock_time.sleep.assert_called_with(1.0)
