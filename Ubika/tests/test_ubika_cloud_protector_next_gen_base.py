from unittest.mock import MagicMock

import httpx
import pytest

from ubika_modules import UbikaModule
from ubika_modules.connector_ubika_cloud_protector_next_gen_base import (
    AuthorizationError,
    AuthorizationTimeoutError,
    FetchEventsException,
    UbikaCloudProtectorNextGenBaseConnector,
    UbikaCloudProtectorNextGenBaseConnectorConfiguration,
)


@pytest.fixture
def trigger(data_storage):
    module = UbikaModule()
    trigger = UbikaCloudProtectorNextGenBaseConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = UbikaCloudProtectorNextGenBaseConnectorConfiguration(
        api_key="some_api_key_here",
        base_url="https://api.ubika.io/",
        namespace="sekoia",
        refresh_token="some_token_here",
        intake_key="intake_key",
        chunk_size=100,
    )
    # Make client.get a MagicMock so we can stub pagination calls
    trigger.client = MagicMock()
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


def test_get_pages_stops_when_token_missing(trigger):
    """
    If the API returns a page with items but no nextPageToken,
    _get_pages should yield exactly that one page and then stop.
    """
    # First (and only) page: 2 dummy items, nextPageToken=None
    page = {"spec": {"items": [{"x": 1}], "nextPageToken": None}}
    trigger.client.get.return_value = httpx.Response(200, json=page)

    pages = list(trigger._get_pages(endpoint="foo", params={"filters.fromDate": 0}))
    assert pages == [[{"x": 1}]]
    # Only a single HTTP call (no second page)
    assert trigger.client.get.call_count == 1


@pytest.mark.parametrize("exc_cls", [AuthorizationError, AuthorizationTimeoutError])
def test_get_pages_raises_on_next_page_auth_errors(trigger, exc_cls):
    """
    If the second fetch (pagination) raises AuthorizationError or Timeout,
    _get_pages must bubble it up.
    """
    # First call returns a valid page with a token
    first = {"spec": {"items": [{"x": 1}], "nextPageToken": "T1"}}
    trigger.client.get.side_effect = [
        httpx.Response(200, json=first),
        exc_cls("auth failed"),
    ]

    with pytest.raises(exc_cls):
        list(trigger._get_pages(endpoint="foo", params={"filters.fromDate": 0}))

    # 2 calls: initial + follow-up
    assert trigger.client.get.call_count == 2
