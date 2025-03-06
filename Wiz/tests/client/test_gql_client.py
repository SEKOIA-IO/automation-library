import datetime

import pytest
from aioresponses import aioresponses

from wiz import WizErrors
from wiz.client.gql_client import WizResult, WizServerError


@pytest.mark.asyncio
async def test_wiz_gql_client_request(http_token, session_faker, wiz_gql_client, auth_url, tenant_url):
    """
    Test WizGqlClient.request method

    Args:
        http_token: WizToken
        session_faker: Faker
        wiz_gql_client: WizGqlClient
        auth_url: str
        tenant_url: str
    """
    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": {"test": "test"}})

        result = await wiz_gql_client.request("query { test }")

        assert result == {"test": "test"}

        await wiz_gql_client.close()


@pytest.mark.asyncio
async def test_wiz_gql_client_get_audit_logs(
    http_token,
    session_faker,
    wiz_gql_client,
    auth_url,
    tenant_url,
    audit_logs_response,
    audit_logs_response_with_next_page,
):
    """
    Test WizGqlClient.get_audit_logs method

    Args:
        http_token: WizHttpToken
        session_faker: Faker
        wiz_gql_client: WizGqlClient
        auth_url: str
        tenant_url: str
        findings_response: dict[str, Any]
        findings_response_with_next_page: dict[str, Any]
    """
    date = datetime.datetime.now()

    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": audit_logs_response_with_next_page})
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": audit_logs_response})

        result = await wiz_gql_client.get_audit_logs(date)
        expected_result = WizResult.from_audit_logs_response(audit_logs_response_with_next_page)
        assert result == expected_result

        result = await wiz_gql_client.get_audit_logs(date, expected_result.end_cursor)
        expected_result = WizResult.from_audit_logs_response(audit_logs_response)
        assert result == expected_result

        await wiz_gql_client.close()


@pytest.mark.asyncio
async def test_wiz_gql_client_get_audit_logs_error(
    http_token,
    session_faker,
    wiz_gql_client,
    auth_url,
    tenant_url,
):
    """
    Test WizGqlClient.get_audit_logs method

    Args:
        http_token: WizHttpToken
        session_faker: Faker
        wiz_gql_client: WizGqlClient
        auth_url: str
        tenant_url: str
    """
    date = datetime.datetime.now()

    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"errors": ["some_error"]})

        with pytest.raises(WizErrors):
            await wiz_gql_client.get_audit_logs(date)

        await wiz_gql_client.close()


@pytest.mark.asyncio
async def test_wiz_gql_client_get_audit_logs_error_1(
    http_token,
    session_faker,
    wiz_gql_client,
    auth_url,
    tenant_url,
):
    """
    Test WizGqlClient.get_audit_logs method

    Args:
        http_token: WizHttpToken
        session_faker: Faker
        wiz_gql_client: WizGqlClient
        auth_url: str
        tenant_url: str
    """
    date = datetime.datetime.now()

    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": {"errors": ["some_error"]}})

        with pytest.raises(WizErrors):
            await wiz_gql_client.get_audit_logs(date)

        await wiz_gql_client.close()


@pytest.mark.asyncio
async def test_wiz_gql_client_get_audit_logs_error_2(
    http_token,
    session_faker,
    wiz_gql_client,
    auth_url,
    tenant_url,
):
    """
    Test WizGqlClient.get_audit_logs method

    Args:
        http_token: WizHttpToken
        session_faker: Faker
        wiz_gql_client: WizGqlClient
        auth_url: str
        tenant_url: str
    """
    date = datetime.datetime.now()

    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=500)

        with pytest.raises(WizErrors):
            await wiz_gql_client.get_audit_logs(date)

        await wiz_gql_client.close()


@pytest.mark.asyncio
async def test_wiz_gql_client_get_audit_logs_error_3(
    http_token,
    session_faker,
    wiz_gql_client,
    auth_url,
    tenant_url,
):
    """
    Test WizGqlClient.get_audit_logs method

    Args:
        http_token: WizHttpToken
        session_faker: Faker
        wiz_gql_client: WizGqlClient
        auth_url: str
        tenant_url: str
    """
    date = datetime.datetime.now()

    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=401)

        with pytest.raises(WizServerError):
            await wiz_gql_client.get_audit_logs(date)

        await wiz_gql_client.close()


@pytest.mark.asyncio
async def test_wiz_gql_client_get_audit_logs_error_4(
    http_token,
    session_faker,
    wiz_gql_client,
    auth_url,
    tenant_url,
):
    """
    Test WizGqlClient.get_audit_logs method

    Args:
        http_token: WizHttpToken
        session_faker: Faker
        wiz_gql_client: WizGqlClient
        auth_url: str
        tenant_url: str
    """
    date = datetime.datetime.now()

    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=403)

        with pytest.raises(WizServerError):
            await wiz_gql_client.get_audit_logs(date)

        await wiz_gql_client.close()


@pytest.mark.asyncio
async def test_wiz_gql_client_get_alerts(
    http_token,
    session_faker,
    wiz_gql_client,
    auth_url,
    tenant_url,
    alerts_response,
    alerts_response_with_next_page,
):
    """
    Test WizGqlClient.get_alerts method

    Args:
        http_token: WizHttpToken
        session_faker: Faker
        wiz_gql_client: WizGqlClient
        auth_url: str
        tenant_url: str
        alerts_response: dict[str, Any]
        alerts_response_with_next_page: dict[str, Any]
    """
    date = datetime.datetime.now()

    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": alerts_response_with_next_page})
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": alerts_response})

        result = await wiz_gql_client.get_alerts(date)
        expected_result = WizResult.from_alerts_response(alerts_response_with_next_page)
        assert result == expected_result

        result = await wiz_gql_client.get_alerts(date, expected_result.end_cursor)
        expected_result = WizResult.from_alerts_response(alerts_response)
        assert result == expected_result

        await wiz_gql_client.close()


@pytest.mark.asyncio
async def test_wiz_gql_client_get_cloud_configuration_findings(
    http_token,
    session_faker,
    wiz_gql_client,
    auth_url,
    tenant_url,
    cloud_configuration_findings_response,
    cloud_configuration_findings_response_with_next_page,
):
    """
    Test WizGqlClient.get_cloud_configuration_findings method

    Args:
        http_token: WizHttpToken
        session_faker: Faker
        wiz_gql_client: WizGqlClient
        auth_url: str
        tenant_url: str
        cloud_configuration_findings_response: dict[str, Any]
        cloud_configuration_findings_response_with_next_page: dict[str, Any]
    """
    date = datetime.datetime.now()

    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(
            tenant_url + "graphql", status=200, payload={"data": cloud_configuration_findings_response_with_next_page}
        )
        mocked_responses.post(
            tenant_url + "graphql", status=200, payload={"data": cloud_configuration_findings_response}
        )

        result = await wiz_gql_client.get_cloud_configuration_findings(date)
        expected_result = WizResult.from_cloud_configuration_findings_response(
            cloud_configuration_findings_response_with_next_page
        )
        assert result == expected_result

        result = await wiz_gql_client.get_cloud_configuration_findings(date, expected_result.end_cursor)
        expected_result = WizResult.from_cloud_configuration_findings_response(cloud_configuration_findings_response)
        assert result == expected_result

        await wiz_gql_client.close()


@pytest.mark.asyncio
async def test_wiz_gql_client_get_cloud_configuration_findings_error(
    http_token,
    session_faker,
    wiz_gql_client,
    auth_url,
    tenant_url,
):
    """
    Test WizGqlClient.get_cloud_configuration_findings method

    Args:
        http_token: WizHttpToken
        session_faker: Faker
        wiz_gql_client: WizGqlClient
        auth_url: str
        tenant_url: str
    """
    date = datetime.datetime.now()

    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"errors": ["some_error"]})

        with pytest.raises(WizErrors):
            await wiz_gql_client.get_cloud_configuration_findings(date)

        await wiz_gql_client.close()


@pytest.mark.asyncio
async def test_wiz_gql_client_get_cloud_configuration_findings_error_1(
    http_token,
    session_faker,
    wiz_gql_client,
    auth_url,
    tenant_url,
):
    """
    Test WizGqlClient.get_cloud_configuration_findings method

    Args:
        http_token: WizHttpToken
        session_faker: Faker
        wiz_gql_client: WizGqlClient
        auth_url: str
        tenant_url: str
    """
    date = datetime.datetime.now()

    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": {"errors": ["some_error"]}})

        with pytest.raises(WizErrors):
            await wiz_gql_client.get_cloud_configuration_findings(date)

        await wiz_gql_client.close()


@pytest.mark.asyncio
async def test_wiz_gql_client_get_vulnerability_findings(
    http_token,
    session_faker,
    wiz_gql_client,
    auth_url,
    tenant_url,
    vulnerability_findings_response,
    vulnerability_findings_response_with_next_page,
):
    """
    Test WizGqlClient.get_vulnerability_findings method

    Args:
        http_token: WizHttpToken
        session_faker: Faker
        wiz_gql_client: WizGqlClient
        auth_url: str
        tenant_url: str
        vulnerability_findings_response: dict[str, Any]
        vulnerability_findings_response_with_next_page: dict[str, Any]
    """
    date = datetime.datetime.now()

    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(
            tenant_url + "graphql", status=200, payload={"data": vulnerability_findings_response_with_next_page}
        )
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": vulnerability_findings_response})

        result = await wiz_gql_client.get_vulnerability_findings(date)
        expected_result = WizResult.from_vulnerability_findings_response(
            vulnerability_findings_response_with_next_page
        )
        assert result == expected_result

        result = await wiz_gql_client.get_vulnerability_findings(date, expected_result.end_cursor)
        expected_result = WizResult.from_vulnerability_findings_response(vulnerability_findings_response)
        assert result == expected_result

        await wiz_gql_client.close()


@pytest.mark.asyncio
async def test_wiz_gql_client_get_vulnerability_findings_error(
    http_token,
    session_faker,
    wiz_gql_client,
    auth_url,
    tenant_url,
):
    """
    Test WizGqlClient.get_vulnerability_findings method

    Args:
        http_token: WizHttpToken
        session_faker: Faker
        wiz_gql_client: WizGqlClient
        auth_url: str
        tenant_url: str
    """
    date = datetime.datetime.now()

    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"errors": ["some_error"]})

        with pytest.raises(WizErrors):
            await wiz_gql_client.get_vulnerability_findings(date)

        await wiz_gql_client.close()


@pytest.mark.asyncio
async def test_wiz_gql_client_get_vulnerability_findings_error_1(
    http_token,
    session_faker,
    wiz_gql_client,
    auth_url,
    tenant_url,
):
    """
    Test WizGqlClient.get_vulnerability_findings method

    Args:
        http_token: WizHttpToken
        session_faker: Faker
        wiz_gql_client: WizGqlClient
        auth_url: str
        tenant_url: str
    """
    date = datetime.datetime.now()

    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": {"errors": ["some_error"]}})

        with pytest.raises(WizErrors):
            await wiz_gql_client.get_vulnerability_findings(date)

        await wiz_gql_client.close()
