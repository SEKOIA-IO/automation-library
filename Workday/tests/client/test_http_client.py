"""Tests for WorkdayClient."""

from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
import re

import pytest
from aioresponses import aioresponses
from faker import Faker

from workday.client.http_client import WorkdayClient
from workday.client.errors import WorkdayAuthError, WorkdayRateLimitError


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
