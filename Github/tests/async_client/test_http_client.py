"""Tests related to github api client."""

import pytest
from aiolimiter import AsyncLimiter
from aioresponses import aioresponses

from github_modules.async_client.http_client import AsyncGithubClient


@pytest.mark.asyncio
async def test_github_client_init_error(session_faker):
    """
    Test GithubClient.init.

    Args:
        session_faker: Faker
    """
    try:
        AsyncGithubClient(session_faker.word(), None, None, session_faker.pyint(), None)

        assert False
    except ValueError:
        assert True


@pytest.mark.asyncio
async def test_github_client_rate_limiter(session_faker):
    """
    Test GithubClient rate limiter.

    Args:
        session_faker: Faker
    """
    assert AsyncGithubClient._rate_limiter is None

    AsyncGithubClient(session_faker.word(), session_faker.word(), None, None, None)

    assert AsyncGithubClient._rate_limiter is None

    async_limiter_1 = AsyncLimiter(1, 1)
    async_limiter_2 = AsyncLimiter(2, 1)

    AsyncGithubClient(session_faker.word(), session_faker.word(), None, None, async_limiter_1)
    assert AsyncGithubClient._rate_limiter == async_limiter_1

    AsyncGithubClient.set_rate_limiter(async_limiter_2)
    assert AsyncGithubClient._rate_limiter == async_limiter_2


@pytest.mark.asyncio
async def test_github_client_token_refresher(session_faker, pem_content):
    """
    Test GithubClient token refresher.

    Args:
        session_faker: Faker
        pem_content: str
    """
    github_client_1 = AsyncGithubClient(session_faker.word(), session_faker.word(), None, None)
    github_client_2 = AsyncGithubClient(session_faker.word(), session_faker.word(), pem_content, None)
    github_client_3 = AsyncGithubClient(session_faker.word(), session_faker.word(), pem_content, session_faker.pyint())

    try:
        await github_client_1._get_token_refresher()

        assert False
    except ValueError:
        assert True

    try:
        await github_client_2._get_token_refresher()

        assert False
    except ValueError:
        assert True

    assert await github_client_3._get_token_refresher() == await github_client_3._get_token_refresher()


@pytest.mark.asyncio
async def test_github_client_auth_headers(session_faker, pem_content):
    """
    Test GithubClient auth headers.

    Args:
        session_faker: Faker
    """
    api_key = session_faker.word()
    organization = session_faker.word()
    github_client_1 = AsyncGithubClient(organization, api_key, None, None)
    github_client_2 = AsyncGithubClient(organization, None, pem_content, session_faker.pyint())

    headers_1 = await github_client_1.get_auth_headers()

    assert headers_1 == {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": "token {0}".format(api_key),
    }

    with aioresponses() as mocked_responses:
        access_tokens_url = session_faker.uri()
        access_token = session_faker.word()
        mocked_responses.get(
            "https://api.github.com/orgs/{0}/installation".format(organization),
            status=200,
            payload={"access_tokens_url": access_tokens_url},
        )

        mocked_responses.post(access_tokens_url, status=200, payload={"token": access_token})

        headers2 = await github_client_2.get_auth_headers()
        assert headers2 == {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": "Bearer {0}".format(access_token),
        }


@pytest.mark.asyncio
async def test_github_client_audit_log_url(session_faker):
    """
    Test GithubClient audit logs url.

    Args:
        session_faker: Faker
    """
    organization = session_faker.word()
    github_client = AsyncGithubClient(organization, session_faker.word(), None, None)

    assert github_client.audit_logs_url == "https://api.github.com/orgs/{0}/audit-log".format(organization)


@pytest.mark.asyncio
async def test_github_client_get_audit_logs_with_api_key(session_faker, github_response, last_timestamp):
    """
    Test GithubClient audit logs url.

    Args:
        session_faker: Faker
        github_response: list[dict[str, Any]]
        last_timestamp: int
    """
    organization = session_faker.word()
    github_client = AsyncGithubClient(organization, session_faker.word(), None, None)

    with aioresponses() as mocked_responses:
        mocked_responses.get(
            github_client.audit_logs_url + "?order=asc&phrase=created%253A%253E{0}".format(last_timestamp),
            status=200,
            payload=github_response,
        )

        audit_logs = await github_client.get_audit_logs(last_timestamp)

        assert audit_logs == github_response


@pytest.mark.asyncio
async def test_github_client_get_audit_logs_with_pem_file_content(
    session_faker,
    pem_content,
    github_response,
    last_timestamp,
):
    """
    Test GithubClient audit logs url.

    Args:
        session_faker: Faker
        pem_content: str
        github_response: list[dict[str, Any]]
        last_timestamp: int
    """
    organization = session_faker.word()
    github_client = AsyncGithubClient(organization, session_faker.word(), pem_content, session_faker.pyint())

    with aioresponses() as mocked_responses:
        access_tokens_url = session_faker.uri()

        mocked_responses.get(
            "https://api.github.com/orgs/{0}/installation".format(organization),
            status=200,
            payload={"access_tokens_url": access_tokens_url},
        )

        mocked_responses.post(access_tokens_url, status=200, payload={"token": session_faker.word()})

        mocked_responses.get(
            github_client.audit_logs_url + "?order=asc&phrase=created%253A%253E{0}".format(last_timestamp),
            status=200,
            payload=github_response,
        )

        audit_logs = await github_client.get_audit_logs(last_timestamp)

        assert audit_logs == github_response
