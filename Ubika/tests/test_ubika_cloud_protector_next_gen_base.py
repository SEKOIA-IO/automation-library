from unittest.mock import MagicMock

import httpx
import pytest

from ubika_modules import UbikaModule
from ubika_modules.connector_ubika_cloud_protector_next_gen_base import (
    FetchEventsException,
    UbikaCloudProtectorNextGenBaseConnector,
)


@pytest.fixture
def trigger(data_storage):
    module = UbikaModule()
    trigger = UbikaCloudProtectorNextGenBaseConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = {
        "namespace": "sekoia",
        "refresh_token": "some_token_here",
        "intake_key": "intake_key",
        "chunk_size": 100,
    }
    yield trigger


def test_handle_response_error(trigger):
    request = httpx.Request("GET", "https://sekoia.io")
    # Handle response error with text
    response = httpx.Response(status_code=500, request=request, text="Internal Error")
    with pytest.raises(FetchEventsException) as m:
        trigger._handle_response_error(response)
    assert "Internal Error" in str(m.value)
    assert "500" in str(m.value)
    # Handle response error with JSON
    response = httpx.Response(status_code=500, request=request, json={"error": "Internal Error"})
    with pytest.raises(FetchEventsException) as m:
        trigger._handle_response_error(response)
    assert "Internal Error" in str(m.value)
    # Should not raise
    response = httpx.Response(status_code=200, request=request, json={"spec": {"items": [], "nextPageToken": None}})
    trigger._handle_response_error(response)
