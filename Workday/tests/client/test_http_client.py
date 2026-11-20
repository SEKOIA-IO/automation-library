"""Tests for WorkdayClient."""

from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
import re

import pytest
from aioresponses import aioresponses
from faker import Faker

from workday.client.http_client import WorkdayClient
from workday.client.errors import WorkdayAuthError, WorkdayError, WorkdayRateLimitError


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Neutralize retry/backoff sleeps so 401/429 tests don't wait real seconds."""

    async def _instant_sleep(*args, **kwargs):
        return None

    monkeypatch.setattr("workday.client.http_client.sleep", _instant_sleep)


@pytest.fixture
def workday_client_faker(faker: Faker) -> WorkdayClient:
    """Return a WorkdayClient instance with fake credentials."""
    return WorkdayClient(
        workday_host=faker.domain_name(),
        tenant_name=faker.word(),
        client_id=faker.pystr(),
        client_secret=faker.pystr(),
        refresh_token=faker.pystr(),
    )


@pytest.mark.asyncio
async def test_get_access_token_caches_token(faker: Faker, workday_client_faker: WorkdayClient):
    """Test token retrieval and caching."""
    token_data = {"access_token": faker.pystr(), "expires_in": 3600}

    with aioresponses() as mocked:
        # Mock needs to be set up before entering client context
        print("Mocking token endpoint:", workday_client_faker.token_endpoint)
        mocked.post(workday_client_faker.token_endpoint, status=200, payload=token_data)

        async with workday_client_faker as client:
            token1 = await client._get_access_token()
            token2 = await client._get_access_token()  # should use cache

            assert token1 == token_data["access_token"]
            assert token2 == token1


@pytest.mark.asyncio
async def test_get_access_token_raises_auth_error(faker: Faker, workday_client_faker: WorkdayClient):
    """Test that 401 during token retrieval raises WorkdayAuthError."""
    with aioresponses() as mocked:
        mocked.post(workday_client_faker.token_endpoint, status=401, payload={"error": "unauthorized"})

        with pytest.raises(WorkdayAuthError):
            async with workday_client_faker as client:
                pass  # Should raise during __aenter__


@pytest.mark.asyncio
async def test_fetch_activity_logs_success(faker: Faker, workday_client_faker: WorkdayClient):
    """Test fetching activity logs successfully."""
    logs = [{"id": 1, "action": "login"}, {"id": 2, "action": "logout"}]
    from_time = datetime.now(timezone.utc)
    to_time = from_time + timedelta(minutes=1)

    with aioresponses() as mocked:
        # Mock token first (called in __aenter__)
        token_data = {"access_token": faker.pystr(), "expires_in": 3600}
        mocked.post(workday_client_faker.token_endpoint, status=200, payload=token_data)

        # Mock activity logs endpoint using regex to allow query-string variants
        url = urljoin(workday_client_faker.base_url + "/", "activityLogging")
        mocked.get(re.compile(rf"^{re.escape(url)}(\?.+)?$"), status=200, payload=logs)

        async with workday_client_faker as client:
            result = await client.fetch_activity_logs(from_time, to_time, limit=10)
            assert result == logs


@pytest.mark.asyncio
async def test_fetch_activity_logs_passes_instances_returned(faker: Faker, workday_client_faker: WorkdayClient):
    """The instancesReturned parameter must be forwarded to the API (no longer hardcoded to 1)."""
    from_time = datetime.now(timezone.utc)
    to_time = from_time + timedelta(minutes=1)

    with aioresponses() as mocked:
        token_data = {"access_token": faker.pystr(), "expires_in": 3600}
        mocked.post(workday_client_faker.token_endpoint, status=200, payload=token_data)

        url = urljoin(workday_client_faker.base_url + "/", "activityLogging")
        mocked.get(re.compile(rf"^{re.escape(url)}(\?.+)?$"), status=200, payload=[])

        async with workday_client_faker as client:
            await client.fetch_activity_logs(from_time, to_time, instances_returned=5)

        sent_urls = [str(key[1]) for key in mocked.requests if key[0] == "GET"]
        assert any("instancesReturned=5" in u for u in sent_urls)


@pytest.mark.asyncio
async def test_fetch_activity_logs_401_retry(faker: Faker, workday_client_faker: WorkdayClient):
    """Test that 401 triggers token refresh and retry."""
    from_time = datetime.now(timezone.utc)
    to_time = from_time + timedelta(minutes=1)

    with aioresponses() as mocked:
        # Initial token for __aenter__
        token1 = faker.pystr()
        mocked.post(
            workday_client_faker.token_endpoint, status=200, payload={"access_token": token1, "expires_in": 3600}
        )

        # Activity logs: first 401, then success
        url = urljoin(workday_client_faker.base_url + "/", "activityLogging")
        mocked.get(re.compile(rf"^{re.escape(url)}(\?.+)?$"), status=401)

        # FIXED: Mock token refresh after 401
        token2 = faker.pystr()
        mocked.post(
            workday_client_faker.token_endpoint, status=200, payload={"access_token": token2, "expires_in": 3600}
        )

        # second registration for same pattern -> success
        mocked.get(re.compile(rf"^{re.escape(url)}(\?.+)?$"), status=200, payload=[{"id": 1}])

        async with workday_client_faker as client:
            result = await client.fetch_activity_logs(from_time, to_time)
            assert result == [{"id": 1}]


@pytest.mark.asyncio
async def test_fetch_activity_logs_429_backoff(faker: Faker, workday_client_faker: WorkdayClient):
    """Test 429 rate limit triggers retry with backoff."""
    from_time = datetime.now(timezone.utc)
    to_time = from_time + timedelta(minutes=1)

    with aioresponses() as mocked:
        # Initial token for __aenter__
        token_data = {"access_token": faker.pystr(), "expires_in": 3600}
        mocked.post(workday_client_faker.token_endpoint, status=200, payload=token_data)

        url = urljoin(workday_client_faker.base_url + "/", "activityLogging")

        # Register two 429s then success (use same regex)
        mocked.get(re.compile(rf"^{re.escape(url)}(\?.+)?$"), status=429)
        mocked.get(re.compile(rf"^{re.escape(url)}(\?.+)?$"), status=429)
        mocked.get(re.compile(rf"^{re.escape(url)}(\?.+)?$"), status=200, payload=[{"id": 42}])

        async with workday_client_faker as client:
            result = await client.fetch_activity_logs(from_time, to_time)
            assert result == [{"id": 42}]


@pytest.mark.asyncio
async def test_fetch_activity_logs_failure_after_retries(faker: Faker, workday_client_faker: WorkdayClient):
    """Test that exceeding retries raises WorkdayRateLimitError."""
    from_time = datetime.now(timezone.utc)
    to_time = from_time + timedelta(minutes=1)

    with aioresponses() as mocked:
        # Initial token for __aenter__
        token_data = {"access_token": faker.pystr(), "expires_in": 3600}
        mocked.post(workday_client_faker.token_endpoint, status=200, payload=token_data)

        url = urljoin(workday_client_faker.base_url + "/", "activityLogging")

        # Always return 429 (three times)
        mocked.get(re.compile(rf"^{re.escape(url)}(\?.+)?$"), status=429)
        mocked.get(re.compile(rf"^{re.escape(url)}(\?.+)?$"), status=429)
        mocked.get(re.compile(rf"^{re.escape(url)}(\?.+)?$"), status=429)

        async with workday_client_faker as client:
            with pytest.raises(WorkdayRateLimitError):
                await client.fetch_activity_logs(from_time, to_time)


# ---------------------------------------------------------------------------
# Token endpoint / caching edge cases
# ---------------------------------------------------------------------------


def test_token_endpoint_uses_explicit_override(faker: Faker):
    """An explicit token_endpoint takes precedence over the derived URL."""
    explicit = "https://auth.example.com/token"
    client = WorkdayClient(
        workday_host=faker.domain_name(),
        tenant_name=faker.word(),
        client_id=faker.pystr(),
        client_secret=faker.pystr(),
        refresh_token=faker.pystr(),
        token_endpoint=explicit,
    )
    assert client.token_endpoint == explicit


@pytest.mark.asyncio
async def test_get_access_token_without_session_raises(workday_client_faker: WorkdayClient):
    """Requesting a token before the session is created is a programming error."""
    with pytest.raises(WorkdayError, match="HTTP session not initialized"):
        await workday_client_faker._get_access_token()


@pytest.mark.asyncio
async def test_fetch_activity_logs_without_session_raises(workday_client_faker: WorkdayClient):
    """Fetching before entering the context manager raises rather than crashing on None."""
    from_time = datetime.now(timezone.utc)
    to_time = from_time + timedelta(minutes=1)
    with pytest.raises(WorkdayError, match="HTTP session not initialized"):
        await workday_client_faker.fetch_activity_logs(from_time, to_time)


@pytest.mark.asyncio
async def test_get_access_token_refreshes_when_expired(faker: Faker, workday_client_faker: WorkdayClient):
    """An expired cached token triggers a fresh token request."""
    with aioresponses() as mocked:
        mocked.post(
            workday_client_faker.token_endpoint,
            status=200,
            payload={"access_token": "token-1", "expires_in": 3600},
        )
        mocked.post(
            workday_client_faker.token_endpoint,
            status=200,
            payload={"access_token": "token-2", "expires_in": 3600},
        )

        async with workday_client_faker as client:
            first = await client._get_access_token()
            # Force the cached token to look expired.
            client._token_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            second = await client._get_access_token()

    assert first == "token-1"
    assert second == "token-2"


@pytest.mark.asyncio
async def test_get_access_token_non_200_raises_workday_error(faker: Faker, workday_client_faker: WorkdayClient):
    """A non-401 error status on the token endpoint raises WorkdayError."""
    with aioresponses() as mocked:
        mocked.post(workday_client_faker.token_endpoint, status=500, payload={"error": "boom"})

        with pytest.raises(WorkdayError, match="Token request failed"):
            async with workday_client_faker:
                pass


# ---------------------------------------------------------------------------
# Response-shape parsing in fetch_activity_logs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["data", "ActivityLogEntry", "Report_Entry", "items", "activityLogs"])
async def test_fetch_activity_logs_extracts_known_dict_keys(
    faker: Faker, workday_client_faker: WorkdayClient, key: str
):
    """Events are pulled from any of the recognised container keys in a dict response."""
    from_time = datetime.now(timezone.utc)
    to_time = from_time + timedelta(minutes=1)
    events = [{"taskId": "t1"}, {"taskId": "t2"}]

    with aioresponses() as mocked:
        mocked.post(
            workday_client_faker.token_endpoint,
            status=200,
            payload={"access_token": faker.pystr(), "expires_in": 3600},
        )
        url = urljoin(workday_client_faker.base_url + "/", "activityLogging")
        mocked.get(re.compile(rf"^{re.escape(url)}(\?.+)?$"), status=200, payload={key: events})

        async with workday_client_faker as client:
            result = await client.fetch_activity_logs(from_time, to_time)

    assert result == events


@pytest.mark.asyncio
async def test_fetch_activity_logs_unknown_dict_keys_returns_empty(faker: Faker, workday_client_faker: WorkdayClient):
    """A dict response with no recognised key yields an empty list."""
    from_time = datetime.now(timezone.utc)
    to_time = from_time + timedelta(minutes=1)

    with aioresponses() as mocked:
        mocked.post(
            workday_client_faker.token_endpoint,
            status=200,
            payload={"access_token": faker.pystr(), "expires_in": 3600},
        )
        url = urljoin(workday_client_faker.base_url + "/", "activityLogging")
        mocked.get(re.compile(rf"^{re.escape(url)}(\?.+)?$"), status=200, payload={"unexpected": [1, 2]})

        async with workday_client_faker as client:
            result = await client.fetch_activity_logs(from_time, to_time)

    assert result == []


@pytest.mark.asyncio
async def test_fetch_activity_logs_bare_list_response(faker: Faker, workday_client_faker: WorkdayClient):
    """A bare JSON list is returned as-is."""
    from_time = datetime.now(timezone.utc)
    to_time = from_time + timedelta(minutes=1)
    events = [{"taskId": "t1"}]

    with aioresponses() as mocked:
        mocked.post(
            workday_client_faker.token_endpoint,
            status=200,
            payload={"access_token": faker.pystr(), "expires_in": 3600},
        )
        url = urljoin(workday_client_faker.base_url + "/", "activityLogging")
        mocked.get(re.compile(rf"^{re.escape(url)}(\?.+)?$"), status=200, payload=events)

        async with workday_client_faker as client:
            result = await client.fetch_activity_logs(from_time, to_time)

    assert result == events


@pytest.mark.asyncio
async def test_fetch_activity_logs_unexpected_type_returns_empty(faker: Faker, workday_client_faker: WorkdayClient):
    """A scalar JSON body (neither dict nor list) is treated as no events."""
    from_time = datetime.now(timezone.utc)
    to_time = from_time + timedelta(minutes=1)

    with aioresponses() as mocked:
        mocked.post(
            workday_client_faker.token_endpoint,
            status=200,
            payload={"access_token": faker.pystr(), "expires_in": 3600},
        )
        url = urljoin(workday_client_faker.base_url + "/", "activityLogging")
        mocked.get(re.compile(rf"^{re.escape(url)}(\?.+)?$"), status=200, payload=42)

        async with workday_client_faker as client:
            result = await client.fetch_activity_logs(from_time, to_time)

    assert result == []


@pytest.mark.asyncio
async def test_fetch_activity_logs_server_error_raises(faker: Faker, workday_client_faker: WorkdayClient):
    """A 500 on the activity endpoint raises WorkdayError."""
    from_time = datetime.now(timezone.utc)
    to_time = from_time + timedelta(minutes=1)

    with aioresponses() as mocked:
        mocked.post(
            workday_client_faker.token_endpoint,
            status=200,
            payload={"access_token": faker.pystr(), "expires_in": 3600},
        )
        url = urljoin(workday_client_faker.base_url + "/", "activityLogging")
        mocked.get(re.compile(rf"^{re.escape(url)}(\?.+)?$"), status=500, body="server exploded")

        async with workday_client_faker as client:
            with pytest.raises(WorkdayError, match="ActivityLogging request failed"):
                await client.fetch_activity_logs(from_time, to_time)


@pytest.mark.asyncio
async def test_fetch_activity_logs_401_exhausts_retries_raises_auth(faker: Faker, workday_client_faker: WorkdayClient):
    """Persistent 401s on the activity endpoint eventually raise WorkdayAuthError."""
    from_time = datetime.now(timezone.utc)
    to_time = from_time + timedelta(minutes=1)

    with aioresponses() as mocked:
        mocked.post(
            workday_client_faker.token_endpoint,
            status=200,
            payload={"access_token": faker.pystr(), "expires_in": 3600},
        )
        url = urljoin(workday_client_faker.base_url + "/", "activityLogging")
        # Every attempt refreshes the token then hits a 401 again.
        for _ in range(3):
            mocked.post(
                workday_client_faker.token_endpoint,
                status=200,
                payload={"access_token": faker.pystr(), "expires_in": 3600},
            )
            mocked.get(re.compile(rf"^{re.escape(url)}(\?.+)?$"), status=401)

        async with workday_client_faker as client:
            with pytest.raises(WorkdayAuthError, match="Unauthorized"):
                await client.fetch_activity_logs(from_time, to_time)


@pytest.mark.asyncio
async def test_fetch_activity_logs_non_list_container_returns_empty(faker: Faker, workday_client_faker: WorkdayClient):
    """A recognised key whose value is not a list is coerced to an empty list."""
    from_time = datetime.now(timezone.utc)
    to_time = from_time + timedelta(minutes=1)

    with aioresponses() as mocked:
        mocked.post(
            workday_client_faker.token_endpoint,
            status=200,
            payload={"access_token": faker.pystr(), "expires_in": 3600},
        )
        url = urljoin(workday_client_faker.base_url + "/", "activityLogging")
        mocked.get(re.compile(rf"^{re.escape(url)}(\?.+)?$"), status=200, payload={"data": {"not": "a list"}})

        async with workday_client_faker as client:
            result = await client.fetch_activity_logs(from_time, to_time)

    assert result == []


def test_log_forwards_to_trigger(faker: Faker):
    """When a trigger is attached, log() delegates to it; otherwise it is a no-op."""
    from unittest.mock import MagicMock

    trigger = MagicMock()
    client = WorkdayClient(
        workday_host=faker.domain_name(),
        tenant_name=faker.word(),
        client_id=faker.pystr(),
        client_secret=faker.pystr(),
        refresh_token=faker.pystr(),
        trigger=trigger,
    )

    client.log("hello", level="warning")
    trigger.log.assert_called_once_with(message="hello", level="warning")


@pytest.mark.asyncio
async def test_aexit_without_session_is_noop(workday_client_faker: WorkdayClient):
    """Exiting the context when no session was opened must not raise."""
    assert workday_client_faker._session is None
    await workday_client_faker.__aexit__(None, None, None)
