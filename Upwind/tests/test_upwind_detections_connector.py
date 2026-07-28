from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from upwind.upwind_detections_connector import UpwindDetectionsConnector


class FakeSecret:
    def __init__(self, value: str) -> None:
        self.value = value

    def get_secret_value(self) -> str:
        return self.value


class FakeResponse:
    def __init__(self, payload: Any, *, should_fail: bool = False) -> None:
        self.payload = payload
        self.should_fail = should_fail

    def raise_for_status(self) -> None:
        if self.should_fail:
            raise RuntimeError("boom")

    async def json(self) -> Any:
        return self.payload


class FakeRequestContext:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    async def __aenter__(self) -> FakeResponse:
        return self.response

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def get(self, **kwargs: Any) -> FakeRequestContext:
        self.calls.append(kwargs)
        return FakeRequestContext(self.response)


def build_connector(response: FakeResponse) -> tuple[UpwindDetectionsConnector, FakeSession]:
    connector = object.__new__(UpwindDetectionsConnector)
    connector.configuration = {
        "frequency": 60,
        "intake_key": "intake-key",
        "page_size": 42,
    }
    connector.module = SimpleNamespace(
        configuration=SimpleNamespace(base_url="https://api.upwind.io", api_token=FakeSecret("token"))
    )
    connector.request_timeout = 30
    session = FakeSession(response)
    connector.session = session
    return connector, session


@pytest.mark.asyncio
async def test_fetch_page_handles_list_payload() -> None:
    connector, session = build_connector(FakeResponse(payload=[{"id": "a"}]))

    page = await connector.fetch_page(since=datetime(2026, 7, 27, tzinfo=UTC))

    assert page.items == [{"id": "a"}]
    assert page.next_page_token is None

    call = session.calls[0]
    assert call["url"] == "https://api.upwind.io/v1alpha1/detections"
    assert call["params"]["limit"] == 42
    assert call["params"]["updated_after"].endswith("Z")


@pytest.mark.asyncio
async def test_fetch_page_handles_dict_payload_and_pagination() -> None:
    connector, _ = build_connector(
        FakeResponse(payload={"detections": [{"id": "b"}], "next_page_token": "next-token"})
    )

    page = await connector.fetch_page(since=datetime(2026, 7, 27, tzinfo=UTC), page_token="cursor")

    assert page.items == [{"id": "b"}]
    assert page.next_page_token == "next-token"


@pytest.mark.asyncio
async def test_fetch_page_returns_empty_when_payload_shape_is_unknown() -> None:
    connector, _ = build_connector(FakeResponse(payload={"foo": "bar"}))

    page = await connector.fetch_page(since=datetime(2026, 7, 27, tzinfo=UTC))

    assert page.items == []
    assert page.next_page_token is None


@pytest.mark.asyncio
async def test_fetch_page_propagates_http_errors() -> None:
    connector, _ = build_connector(FakeResponse(payload={}, should_fail=True))

    with pytest.raises(RuntimeError, match="boom"):
        await connector.fetch_page(since=datetime(2026, 7, 27, tzinfo=UTC))
