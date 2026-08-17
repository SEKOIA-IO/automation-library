from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from upwind import UpwindConnectorConfig
from upwind.upwind_detections_connector import OAuthTokenProvider, UpwindDetectionsConnector


class FakeResponse:
    def __init__(self, payload: Any, *, should_fail: bool = False) -> None:
        self.payload = payload
        self.should_fail = should_fail

    def raise_for_status(self) -> None:
        if self.should_fail:
            raise RuntimeError("boom")

    def json(self) -> Any:
        return self.payload


class FakeSession:
    def __init__(
        self,
        get_response: FakeResponse,
        *,
        auth_responses: list[FakeResponse] | None = None,
    ) -> None:
        self.get_response = get_response
        self.auth_responses = (
            list(auth_responses)
            if auth_responses is not None
            else [
                FakeResponse(
                    payload={
                        "access_token": "token",
                        "token_type": "Bearer",
                        "expires_in": 3600,
                    }
                )
            ]
        )
        self.get_calls: list[dict[str, Any]] = []
        self.post_calls: list[dict[str, Any]] = []

    def get(self, **kwargs: Any) -> FakeResponse:
        self.get_calls.append(kwargs)
        return self.get_response

    def post(self, **kwargs: Any) -> FakeResponse:
        self.post_calls.append(kwargs)
        if not self.auth_responses:
            raise RuntimeError("No fake auth response available")
        return self.auth_responses.pop(0)


def build_connector(
    response: FakeResponse,
    *,
    auth_responses: list[FakeResponse] | None = None,
    configuration: UpwindConnectorConfig | None = None,
) -> tuple[UpwindDetectionsConnector, FakeSession]:
    connector = object.__new__(UpwindDetectionsConnector)
    connector.configuration = configuration or UpwindConnectorConfig(frequency=60, intake_key="intake-key")
    connector.module = SimpleNamespace(
        configuration=SimpleNamespace(
            base_url="https://api.upwind.io",
            auth_url="https://auth.upwind.io/oauth/token",
            client_id="client-id",
            client_secret="client-secret",
            organization_id="org_test123",
        )
    )
    connector.request_timeout = 30
    connector._oauth_provider = OAuthTokenProvider()

    session = FakeSession(response, auth_responses=auth_responses)
    connector._http_session = session
    return connector, session


def test_fetch_detections_uses_time_window_and_array_contract() -> None:
    connector, session = build_connector(
        FakeResponse(payload=[{"id": "a"}]),
        configuration=UpwindConnectorConfig(
            frequency=60,
            intake_key="intake-key",
        ),
    )

    since = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)

    detections = connector.fetch_detections(since=since)

    assert detections == [{"id": "a"}]

    call = session.get_calls[0]
    assert call["url"] == "https://api.upwind.io/v1/organizations/org_test123/threat-detections"
    assert call["headers"]["Authorization"] == "Bearer token"
    assert call["params"]["min-last-seen-time"] == "2026-07-27T10:00:00Z"
    assert set(call["params"]) == {"min-last-seen-time"}
    assert "max-last-seen-time" not in call["params"]
    assert "updated_after" not in call["params"]
    assert "page_token" not in call["params"]
    assert "limit" not in call["params"]

    auth_call = session.post_calls[0]
    assert auth_call["url"] == "https://auth.upwind.io/oauth/token"
    assert auth_call["data"] == {
        "client_id": "client-id",
        "client_secret": "client-secret",
        "audience": "https://api.upwind.io",
        "grant_type": "client_credentials",
    }


def test_fetch_detections_drops_microseconds_from_time_window() -> None:
    connector, session = build_connector(FakeResponse(payload=[]))

    since = datetime(2026, 8, 7, 13, 50, 17, 110669, tzinfo=UTC)

    connector.fetch_detections(since=since)

    call = session.get_calls[0]
    assert call["params"]["min-last-seen-time"] == "2026-08-07T13:50:17Z"


def test_fetch_detections_reuses_cached_access_token() -> None:
    connector, session = build_connector(FakeResponse(payload=[]))

    connector.fetch_detections(
        since=datetime(2026, 7, 27, 0, 0, tzinfo=UTC),
    )
    connector.fetch_detections(
        since=datetime(2026, 7, 27, 0, 0, tzinfo=UTC),
    )

    assert len(session.post_calls) == 1
    assert len(session.get_calls) == 2


def test_fetch_detections_refreshes_access_token_before_expiry() -> None:
    connector, session = build_connector(
        FakeResponse(payload=[]),
        auth_responses=[
            FakeResponse(
                payload={
                    "access_token": "refreshed-token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                }
            )
        ],
    )
    connector._oauth_provider.access_token = "Bearer stale-token"
    connector._oauth_provider.expires_at = datetime.now(UTC) + timedelta(seconds=120)

    connector.fetch_detections(
        since=datetime(2026, 7, 27, 0, 0, tzinfo=UTC),
    )

    assert len(session.post_calls) == 1
    assert session.get_calls[0]["headers"]["Authorization"] == "Bearer refreshed-token"


@pytest.mark.parametrize(
    ("response", "auth_responses", "expected_exc", "match"),
    [
        pytest.param(
            FakeResponse(payload=[]),
            [FakeResponse(payload={"expires_in": 3600})],
            ValueError,
            "access_token",
            id="invalid_auth_payload",
        ),
        pytest.param(
            FakeResponse(payload={"foo": "bar"}),
            None,
            ValueError,
            "JSON array",
            id="non_list_payload",
        ),
        pytest.param(
            FakeResponse(payload=["bad-item"]),
            None,
            ValueError,
            "contain objects",
            id="non_object_event_items",
        ),
        pytest.param(
            FakeResponse(payload={}, should_fail=True),
            None,
            RuntimeError,
            "boom",
            id="http_errors",
        ),
    ],
)
def test_fetch_detections_error_paths(
    response: FakeResponse,
    auth_responses: list[FakeResponse] | None,
    expected_exc: type[Exception],
    match: str,
) -> None:
    connector, _ = build_connector(response, auth_responses=auth_responses)

    with pytest.raises(expected_exc, match=match):
        connector.fetch_detections(
            since=datetime(2026, 7, 27, 0, 0, tzinfo=UTC),
        )
