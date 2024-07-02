"""All necessary tests for http client."""

from typing import Any

import pytest
from aioresponses import aioresponses
from faker import Faker

from client.http_client import BitsightClient


@pytest.fixture
def findings(session_faker: Faker) -> list[dict[str, Any]]:
    """
    Get findings.

    Args:
        session_faker: Faker

    Returns:
        list[dict[str, Any]]:
    """
    return [session_faker.pydict(allowed_types=[str, int]) for _ in range(10)]


@pytest.fixture
def api_token(session_faker: Faker) -> str:
    """
    Get API token.

    Args:
        session_faker: Faker

    Returns:
        str:
    """
    return session_faker.word()


@pytest.fixture
def company_id(session_faker: Faker) -> str:
    """
    Get API token.

    Args:
        session_faker: Faker

    Returns:
        str:
    """
    return session_faker.word()


@pytest.mark.asyncio
async def test_get_url_1(company_id: str) -> None:
    """
    Test get_url with no parameters.

    Args:
        company_id: str
    """
    url = BitsightClient.get_url(company_id)

    assert str(url) == f"https://api.bitsighttech.com/ratings/v1/companies/{company_id}/findings"


@pytest.mark.asyncio
async def test_get_url_2(company_id: str, session_faker: Faker) -> None:
    """
    Test get_url with last_seen parameter.

    Args:
        company_id: str
        session_faker: Faker
    """
    last_seen = session_faker.word()
    url = BitsightClient.get_url(company_id, last_seen)

    assert str(url) == f"https://api.bitsighttech.com/ratings/v1/companies/{company_id}/findings?last_seen={last_seen}"


@pytest.mark.asyncio
async def test_get_url_3(company_id: str, session_faker: Faker) -> None:
    """
    Test get_url with offset parameter.

    Args:
        company_id: str
        session_faker: Faker
    """
    offset = session_faker.random_int()
    last_seen = session_faker.word()
    url = BitsightClient.get_url(company_id, last_seen=last_seen, offset=offset)

    expected = "https://api.bitsighttech.com/ratings/v1/companies/{0}/findings?last_seen={1}&offset={2}".format(
        company_id, last_seen, offset
    )

    assert str(url) == expected


@pytest.mark.asyncio
async def test_get_findings_raises_value_error_1(api_token: str, company_id: str, session_faker: Faker) -> None:
    """
    Test get_findings with value error if missing all the parameters.

    Args:
        api_token: str
        company_id: str
        session_faker: Faker
    """
    client = BitsightClient(api_token)

    with pytest.raises(ValueError):
        await client.get_findings()


@pytest.mark.asyncio
async def test_get_findings_raises_value_if_error_http_status(
    api_token: str, company_id: str, session_faker: Faker
) -> None:
    """
    Test get_findings with no results.

    Args:
        api_token: str
        company_id: str
        session_faker: Faker
    """
    client = BitsightClient(api_token)

    with aioresponses() as mocked_responses:
        mocked_responses.get(
            f"https://api.bitsighttech.com/ratings/v1/companies/{company_id}/findings",
            body="error",
            status=300,
        )

        with pytest.raises(ValueError) as error:
            await client.get_findings(company_id)

        assert "Failed to get findings: 300: error" in str(error)


@pytest.mark.asyncio
async def test_get_findings_1(
    api_token: str, company_id: str, findings: list[dict[str, Any]], session_faker: Faker
) -> None:
    """
    Test get_findings with empty next url result.

    Args:
        api_token: str
        company_id: str
        findings: list[dict[str, Any]]
        session_faker: Faker
    """
    client = BitsightClient(api_token)

    with aioresponses() as mocked_responses:
        mocked_responses.get(
            f"https://api.bitsighttech.com/ratings/v1/companies/{company_id}/findings",
            payload={"results": findings},
        )

        result, url = await client.get_findings(company_id)

        assert result == findings
        assert url is None


@pytest.mark.asyncio
async def test_get_findings_2(
    api_token: str, company_id: str, findings: list[dict[str, Any]], session_faker: Faker
) -> None:
    """
    Test get_findings with next url result.

    Args:
        api_token: str
        company_id: str
        findings: list[dict[str, Any]]
        session_faker: Faker
    """
    client = BitsightClient(api_token)

    with aioresponses() as mocked_responses:
        next_url = session_faker.uri()

        mocked_responses.get(
            f"https://api.bitsighttech.com/ratings/v1/companies/{company_id}/findings",
            payload={"links": {"next": next_url}, "results": findings},
        )

        result, url = await client.get_findings(company_id)

        assert result == findings
        assert url == next_url


@pytest.mark.asyncio
async def test_findings_result_complex(
    api_token: str, company_id: str, findings: list[dict[str, Any]], session_faker: Faker
) -> None:
    """
    Test findings_result.

    Args:
        api_token: str
        company_id: str
        findings: list[dict[str, Any]]
        session_faker: Faker
    """
    client = BitsightClient(api_token)

    findings_1 = [session_faker.pydict(allowed_types=[str, int]) for _ in range(10)]
    next_url_1 = session_faker.uri()

    findings_2 = [session_faker.pydict(allowed_types=[str, int]) for _ in range(10)]
    next_url_2 = session_faker.uri()

    findings_3 = [session_faker.pydict(allowed_types=[str, int]) for _ in range(10)]

    with aioresponses() as mocked_responses:
        mocked_responses.get(
            next_url_2,
            payload={"results": findings_3},
            repeat=True,
        )

        mocked_responses.get(
            next_url_1,
            payload={"links": {"next": next_url_2}, "results": findings_2},
            repeat=True,
        )

        mocked_responses.get(
            f"https://api.bitsighttech.com/ratings/v1/companies/{company_id}/findings",
            payload={"links": {"next": next_url_1}, "results": findings_1},
            repeat=True,
        )

        result = []

        async for finding in client.findings_result(company_id):
            result.append(finding)

        assert result == findings_1 + findings_2 + findings_3
