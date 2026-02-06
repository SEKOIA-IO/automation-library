"""Tests related to token refresher."""

import pytest
from aioresponses import aioresponses

from github_modules.async_client.token_refresher import PemGithubTokenRefresher


@pytest.mark.asyncio
async def test_github_refresher_refresh_token(base_url, session_faker, pem_content):
    """
    Test GithubTokenRefresher.refresh_token.

    Args:
        session_faker: Faker
        pem_content: str
    """
    expected_result = session_faker.word()
    organization = session_faker.word()
    access_tokens_url = session_faker.uri()

    with aioresponses() as mocked_responses:
        mocked_responses.get(
            "{0}/orgs/{1}/installation".format(base_url, organization),
            status=200,
            payload={"access_tokens_url": access_tokens_url},
        )

        mocked_responses.post(access_tokens_url, status=200, payload={"token": expected_result})

        token_refresher = PemGithubTokenRefresher(
            base_url,
            pem_content,
            organization,
            session_faker.pyint(),
        )

        await token_refresher.refresh_token()

        assert token_refresher._token is not None
        assert token_refresher._token == expected_result

        await token_refresher.close()


@pytest.mark.asyncio
async def test_github_refresher_get_token(base_url, session_faker, pem_content):
    """
    Test GithubTokenRefresher.get_token.

    Args:
        session_faker: Faker
        pem_content: str
    """
    expected_result = session_faker.word()
    organization = session_faker.word()
    access_tokens_url = session_faker.uri()

    with aioresponses() as mocked_responses:
        mocked_responses.get(
            "{0}/orgs/{1}/installation".format(base_url, organization),
            status=200,
            payload={"access_tokens_url": access_tokens_url},
        )

        mocked_responses.post(access_tokens_url, status=200, payload={"token": expected_result})

        token_refresher = PemGithubTokenRefresher(
            base_url,
            pem_content,
            organization,
            session_faker.pyint(),
        )

        assert token_refresher._token is None

        result = await token_refresher.get_access_token()

        assert token_refresher._token is not None
        assert token_refresher._token == expected_result
        assert token_refresher._token == result

        await token_refresher.close()


@pytest.mark.asyncio
async def test_github_refresher_incorrect_params(base_url, session_faker, pem_content):
    """
    Test GithubTokenRefresher.init.

    Args:
        session_faker: Faker
        pem_content: str
    """
    try:
        PemGithubTokenRefresher(base_url, pem_content, session_faker.word(), session_faker.pyint(), 601)

        assert False
    except ValueError:
        assert True


@pytest.mark.asyncio
async def test_github_token_refresher_instance(base_url, session_faker, pem_content):
    """
    Test PemGithubTokenRefresher.instance method.

    Args:
        session_faker: Faker
        pem_content: str
    """
    app_id = session_faker.pyint()
    organization = session_faker.word()
    different_organization = session_faker.word()
    other_base_url = "https://other.example.com"

    instance1 = await PemGithubTokenRefresher.instance(base_url, pem_content, organization, app_id)
    instance2 = await PemGithubTokenRefresher.instance(base_url, pem_content, organization, app_id)
    instance3 = await PemGithubTokenRefresher.instance(base_url, pem_content, different_organization, app_id)
    instance4 = await PemGithubTokenRefresher.instance(other_base_url, pem_content, organization, app_id)

    assert instance1.base_url == base_url
    assert instance1.pem_file == pem_content
    assert instance1.organization == organization
    assert instance1.app_id == app_id

    assert instance1 is instance2
    assert instance1.base_url == instance2.base_url
    assert instance1.pem_file == instance2.pem_file
    assert instance1.organization == instance2.organization
    assert instance1.app_id == instance2.app_id

    assert instance3 is not instance1
    assert instance3.base_url == base_url
    assert instance3.pem_file == instance1.pem_file
    assert instance3.app_id == instance1.app_id
    assert instance3.organization == different_organization

    assert instance4 is not instance1
    assert instance4.base_url == other_base_url
    assert instance4.organization == organization
    assert instance4.app_id == app_id

    await instance1.close()
    await instance2.close()
    await instance3.close()
    await instance4.close()
