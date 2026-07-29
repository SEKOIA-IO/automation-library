from contextlib import asynccontextmanager
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
        configuration=SimpleNamespace(
            base_url="https://api.upwind.io",
            api_token=FakeSecret("token"),
            organization_id="org_test123"
        )
    )
    connector.request_timeout = 30
    session = FakeSession(response)

    @asynccontextmanager
    async def fake_session_context() -> Any:
        yield session

    connector.session = fake_session_context
    return connector, session


@pytest.mark.asyncio
async def test_fetch_page_handles_list_payload() -> None:
    connector, session = build_connector(FakeResponse(payload=[{"id": "a"}]))

    page = await connector.fetch_page(since=datetime(2026, 7, 27, tzinfo=UTC))

    assert page.items == [{"id": "a"}]
    assert page.next_page_token is None

    call = session.calls[0]
    assert call["url"] == "https://api.upwind.io/v1/organizations/org_test123/threat-detections"
    assert call["params"]["limit"] == 42
    assert call["params"]["updated_after"].endswith("Z")


@pytest.mark.asyncio
async def test_fetch_page_handles_dict_payload_and_pagination() -> None:
    connector, session = build_connector(
        FakeResponse(payload={"threat-detections": [{"id": "b"}], "next_page_token": "next-token"})
    )

    page = await connector.fetch_page(since=datetime(2026, 7, 27, tzinfo=UTC), page_token="cursor")

    assert page.items == [{"id": "b"}]
    assert page.next_page_token == "next-token"

    call = session.calls[0]
    assert call["url"] == "https://api.upwind.io/v1/organizations/org_test123/threat-detections"
    assert call["params"]["limit"] == 42
    assert call["params"]["page_token"] == "cursor"
    assert call["params"]["updated_after"].endswith("Z")


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


# Integration tests - validating API v1 format compliance
@pytest.mark.asyncio
async def test_fetch_page_with_threat_detections_key_in_dict() -> None:
    """Test that API v1 dict response format is correctly parsed."""
    connector, _ = build_connector(
        FakeResponse(
            payload={
                "threat-detections": [
                    {"id": "det-001", "severity": "high"},
                    {"id": "det-002", "severity": "critical"},
                ],
                "next_page_token": "page-2-token",
            }
        )
    )

    page = await connector.fetch_page(since=datetime(2026, 7, 27, tzinfo=UTC))

    assert len(page.items) == 2
    assert page.items[0]["id"] == "det-001"
    assert page.next_page_token == "page-2-token"


@pytest.mark.asyncio
async def test_fetch_page_rejects_wrong_keys() -> None:
    """Test that parsing is strict and only accepts 'threat-detections' key."""
    connector, _ = build_connector(
        FakeResponse(
            payload={
                "detections": [{"id": "wrong-key"}],  # Wrong key, should be ignored
                "results": [{"id": "also-wrong"}],    # Wrong key, should be ignored
            }
        )
    )

    page = await connector.fetch_page(since=datetime(2026, 7, 27, tzinfo=UTC))

    # Should be empty because threat-detections key is missing
    assert page.items == []
    assert page.next_page_token is None


@pytest.mark.asyncio
async def test_fetch_page_pagination_with_next_page_token() -> None:
    """Test that pagination token is correctly extracted from API response."""
    connector, _ = build_connector(
        FakeResponse(
            payload={
                "threat-detections": [{"id": "det-1"}],
                "next_page_token": "cursor-abc123",
            }
        )
    )

    page = await connector.fetch_page(since=datetime(2026, 7, 27, tzinfo=UTC))

    assert page.next_page_token == "cursor-abc123"

    # Verify the pagination token is used in next request
    connector2, session2 = build_connector(FakeResponse(payload={"threat-detections": []}))
    await connector2.fetch_page(since=datetime(2026, 7, 27, tzinfo=UTC), page_token="cursor-abc123")

    call = session2.calls[0]
    assert call["params"]["page_token"] == "cursor-abc123"


@pytest.mark.asyncio
async def test_fetch_page_handles_missing_next_page_token() -> None:
    """Test that missing next_page_token is handled gracefully."""
    connector, _ = build_connector(
        FakeResponse(
            payload={
                "threat-detections": [{"id": "det-1"}],
                # No next_page_token field - end of pagination
            }
        )
    )

    page = await connector.fetch_page(since=datetime(2026, 7, 27, tzinfo=UTC))

    assert page.items == [{"id": "det-1"}]
    assert page.next_page_token is None


@pytest.mark.asyncio
async def test_fetch_page_with_empty_threat_detections_array() -> None:
    """Test that empty threat-detections array is handled correctly."""
    connector, _ = build_connector(
        FakeResponse(payload={"threat-detections": []})
    )

    page = await connector.fetch_page(since=datetime(2026, 7, 27, tzinfo=UTC))

    assert page.items == []
    assert page.next_page_token is None


@pytest.mark.asyncio
async def test_fetch_page_validates_threat_detections_is_list() -> None:
    """Test that threat-detections must be a list, not other types."""
    connector, _ = build_connector(
        FakeResponse(
            payload={
                "threat-detections": "not-a-list",  # Invalid: should be list
            }
        )
    )

    page = await connector.fetch_page(since=datetime(2026, 7, 27, tzinfo=UTC))

    # Should return empty because threat-detections is not a list
    assert page.items == []
    assert page.next_page_token is None
