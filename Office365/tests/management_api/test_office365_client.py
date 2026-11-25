import time
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlencode

import orjson
import pytest
from aioresponses import aioresponses

from office365.management_api.errors import (
    ApplicationAuthenticationFailed,
    FailedToActivateSomeO365Subscriptions,
    FailedToGetO365AuditContent,
    FailedToGetO365SubscriptionContents,
    FailedToListO365Subscriptions,
    SessionClosedError,
)
from office365.management_api.office365_client import Office365API

EXPECTED_SUBSCRIPTIONS = {"Audit.AzureActiveDirectory", "Audit.SharePoint", "Audit.General", "Audit.Exchange"}
BUSINESS_ERROR = orjson.dumps({"error": {"code": "error_code", "message": "error message"}})
TENANT_NOT_FOUND_ERROR = orjson.dumps(
    {
        "error": {
            "code": "AF10001",
            "message": "StartSubscription failed. Exception: DataServiceException: Tenant foo does not exist.",
        }
    }
)
ALREADY_ENABLED_ERROR = orjson.dumps(
    {"error": {"code": "AF20024", "message": "The subscription is already enabled. No property change."}}
)
CONTENT_URI = "https://manage.office.com/api/v1.0/f28ab78a-d401-4060-8012-736e373933eb/activity/feed/audit/42$04"


def make_content(index: int) -> dict:
    return {
        "contentType": "Audit.SharePoint",
        "contentId": f"content-{index}",
        "contentUri": f"{CONTENT_URI}{index}",
        "contentCreated": "2015-05-23T17:35:00.000Z",
        "contentExpiration": "2015-05-30T17:35:00.000Z",
    }


@pytest.fixture
def mocked_responses():
    with aioresponses() as m:
        yield m


@pytest.fixture
def base_url(tenant_id):
    return f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed"


@pytest.fixture
async def client(mock_azure_authentication, tenant_id):
    client = Office365API(client_id="client_id", client_secret="client_secret", tenant_id=tenant_id)
    yield client
    await client.close()


def mock_list_subscriptions(mocked_responses, base_url, enabled: list[str]) -> None:
    mocked_responses.get(
        f"{base_url}/subscriptions/list",
        status=200,
        body=orjson.dumps([{"contentType": content_type, "status": "enabled"} for content_type in enabled]),
    )


def mock_start_subscription(mocked_responses, base_url, content_type: str, status: int, body: bytes | str) -> None:
    mocked_responses.post(
        f"{base_url}/subscriptions/start?contentType={content_type}",
        status=status,
        body=body,
    )


@pytest.mark.parametrize(
    "auth_fixture,expected_message",
    [
        ("mock_azure_authentication_no_access_token", "Failed to get access token"),
        ("mock_azure_authentication_wrong_token_type", "Bearer Authentication not supported"),
    ],
)
async def test_authentication_failure(request, mocked_responses, tenant_id, auth_fixture, expected_message):
    request.getfixturevalue(auth_fixture)
    client = Office365API(client_id="client_id", client_secret="client_secret", tenant_id=tenant_id)

    try:
        with pytest.raises(ApplicationAuthenticationFailed, match=expected_message):
            await client.activate_subscriptions()
    finally:
        await client.close()


@pytest.mark.parametrize(
    "already_enabled,start_status,start_body",
    [
        pytest.param([], 200, orjson.dumps({"status": "enabled"}), id="all_activated"),
        pytest.param([], 400, ALREADY_ENABLED_ERROR, id="all_already_enabled_on_start"),
        pytest.param([], 200, "", id="empty_body"),
        pytest.param([], 200, "not json", id="invalid_json_body"),
        pytest.param(["Audit.SharePoint", "Audit.General"], 200, orjson.dumps({}), id="some_listed_as_enabled"),
        pytest.param(sorted(EXPECTED_SUBSCRIPTIONS), 200, "", id="all_listed_as_enabled"),
    ],
)
async def test_activate_subscriptions_should_succeed(
    client, mocked_responses, base_url, already_enabled, start_status, start_body
):
    mock_list_subscriptions(mocked_responses, base_url, already_enabled)
    for content_type in EXPECTED_SUBSCRIPTIONS - set(already_enabled):
        mock_start_subscription(mocked_responses, base_url, content_type, start_status, start_body)

    assert await client.activate_subscriptions() == EXPECTED_SUBSCRIPTIONS


@pytest.mark.parametrize(
    "status,body,expected_in_error,tenant_not_provisioned",
    [
        pytest.param(200, BUSINESS_ERROR, "error_code='error_code'", False, id="business_error"),
        pytest.param(400, "", "status_code='400'", False, id="http_error"),
        pytest.param(400, TENANT_NOT_FOUND_ERROR, "does not exist", True, id="tenant_not_provisioned"),
    ],
)
async def test_activate_subscriptions_should_continue_after_a_failure(
    client, mocked_responses, base_url, status, body, expected_in_error, tenant_not_provisioned
):
    """A failure on one content type must not prevent the activation of the other content types."""
    mock_list_subscriptions(mocked_responses, base_url, [])
    mock_start_subscription(mocked_responses, base_url, "Audit.General", status, body)
    for content_type in EXPECTED_SUBSCRIPTIONS - {"Audit.General"}:
        mock_start_subscription(mocked_responses, base_url, content_type, 200, orjson.dumps({}))

    with pytest.raises(FailedToActivateSomeO365Subscriptions) as exc_info:
        await client.activate_subscriptions()

    error = exc_info.value
    assert set(error.failures) == {"Audit.General"}
    assert error.active_content_types == EXPECTED_SUBSCRIPTIONS - {"Audit.General"}
    assert error.is_tenant_not_provisioned is tenant_not_provisioned
    assert "content_type='Audit.General'" in str(error)
    assert expected_in_error in str(error)


async def test_list_subscriptions_should_succeed(client, mocked_responses, base_url):
    mocked_responses.get(
        f"{base_url}/subscriptions/list",
        status=200,
        body=orjson.dumps(
            [
                {"contentType": "Audit.SharePoint", "status": "enabled"},
                {"contentType": "Audit.Exchange", "status": "Enabled"},
                {"contentType": "Audit.General", "status": "disabled"},
            ]
        ),
    )

    assert sorted(await client.list_subscriptions()) == ["Audit.Exchange", "Audit.SharePoint"]


@pytest.mark.parametrize(
    "status,body",
    [
        pytest.param(200, BUSINESS_ERROR, id="business_error"),
        pytest.param(400, "", id="http_error"),
    ],
)
async def test_list_subscriptions_should_raise_on_error(client, mocked_responses, base_url, status, body):
    mocked_responses.get(f"{base_url}/subscriptions/list", status=status, body=body)

    with pytest.raises(FailedToListO365Subscriptions):
        await client.list_subscriptions()


@pytest.mark.parametrize(
    "start_time,end_time,publisher_id",
    [
        pytest.param(None, None, None, id="no_parameters"),
        pytest.param(
            datetime(2026, 11, 24, tzinfo=UTC), datetime(2026, 11, 25, tzinfo=UTC), None, id="datetime_parameters"
        ),
        pytest.param("2026-11-24T00:00:00", "2026-11-25T00:00:00", "publisher", id="str_parameters_and_publisher"),
    ],
)
async def test_get_subscription_contents_should_succeed(
    client, mocked_responses, base_url, start_time, end_time, publisher_id
):
    client._publisher_id = publisher_id
    params: dict[str, str] = {"contentType": "Audit.SharePoint"}
    if publisher_id:
        params["PublisherIdentifier"] = publisher_id
    if start_time:
        params["startTime"] = start_time if isinstance(start_time, str) else start_time.isoformat("T")
    if end_time:
        params["endTime"] = end_time if isinstance(end_time, str) else end_time.isoformat("T")
    url = f"{base_url}/subscriptions/content?{urlencode(params)}"
    mocked_responses.get(url, status=200, body=orjson.dumps([make_content(1), make_content(2)]))

    pages = [page async for page in client.get_subscription_contents("Audit.SharePoint", start_time, end_time)]

    assert pages == [[make_content(1), make_content(2)]]
    mocked_responses.assert_called_with(url, headers={"Authorization": "Bearer access_token"})


async def test_get_subscription_contents_with_pagination_should_succeed(client, mocked_responses, base_url):
    next_page_uri = f"{base_url}/subscriptions/content?contentType=Audit.SharePoint&nextPage=2015101900R022885001761"
    mocked_responses.get(
        f"{base_url}/subscriptions/content?contentType=Audit.SharePoint",
        status=200,
        body=orjson.dumps([make_content(1), make_content(2)]),
        headers={"NextPageUri": next_page_uri},
    )
    mocked_responses.get(next_page_uri, status=200, body=orjson.dumps([make_content(3)]))

    pages = [page async for page in client.get_subscription_contents("Audit.SharePoint")]

    assert pages == [[make_content(1), make_content(2)], [make_content(3)]]


@pytest.mark.parametrize(
    "status,body",
    [
        pytest.param(200, BUSINESS_ERROR, id="business_error"),
        pytest.param(400, "", id="http_error"),
    ],
)
async def test_get_subscription_contents_should_raise_on_error(client, mocked_responses, base_url, status, body):
    mocked_responses.get(f"{base_url}/subscriptions/content?contentType=Audit.SharePoint", status=status, body=body)

    with pytest.raises(FailedToGetO365SubscriptionContents):
        await anext(client.get_subscription_contents("Audit.SharePoint"))


async def test_get_content_should_succeed(client, mocked_responses):
    events = [
        {"Id": "80c76bd2-9d81-4c57-a97a-accfc3443dca", "Operation": "PasswordLogonInitialAuthUsingPassword"},
        {"Id": "4e655d3f-35fa-42e0-b050-264b2d255c7a", "Operation": "PasswordLogonInitialAuthUsingPassword"},
    ]
    mocked_responses.get(CONTENT_URI, status=200, body=orjson.dumps(events))

    assert await client.get_content(CONTENT_URI) == events


@pytest.mark.parametrize(
    "status,body",
    [
        pytest.param(200, BUSINESS_ERROR, id="business_error"),
        pytest.param(400, "", id="http_error"),
    ],
)
async def test_get_content_should_raise_on_error(client, mocked_responses, status, body):
    mocked_responses.get(CONTENT_URI, status=status, body=body)

    with pytest.raises(FailedToGetO365AuditContent):
        await client.get_content(CONTENT_URI)


async def call_list_subscriptions(client: Office365API):
    return await client.list_subscriptions()


async def call_activate_subscriptions(client: Office365API):
    return await client.activate_subscriptions()


async def call_get_subscription_contents(client: Office365API):
    return await anext(client.get_subscription_contents("Audit.SharePoint"))


async def call_get_content(client: Office365API):
    return await client.get_content(CONTENT_URI)


CLIENT_CALLS = [
    pytest.param(call_list_subscriptions, "get", id="list_subscriptions"),
    pytest.param(call_activate_subscriptions, "post", id="activate_subscriptions"),
    pytest.param(call_get_subscription_contents, "get", id="get_subscription_contents"),
    pytest.param(call_get_content, "get", id="get_content"),
]


@pytest.mark.parametrize("call,_http_method", CLIENT_CALLS)
async def test_calls_raise_session_closed_after_close(client, call, _http_method):
    await client.close()

    with pytest.raises(SessionClosedError):
        await call(client)


@pytest.mark.parametrize("call,http_method", CLIENT_CALLS)
@pytest.mark.parametrize(
    "runtime_error,expected_exception",
    [
        pytest.param(RuntimeError("Session is closed"), SessionClosedError, id="session_closed"),
        pytest.param(RuntimeError("Something else"), RuntimeError, id="other_runtime_error"),
    ],
)
async def test_calls_translate_runtime_errors(client, call, http_method, runtime_error, expected_exception):
    """A RuntimeError raised mid-request is translated only when it is about a closed session."""
    # Skip token refresh so we exercise the request path, not _authenticate_client.
    client._token_expiration = time.time() + 3600
    client.list_subscriptions = AsyncMock(return_value=[]) if http_method == "post" else client.list_subscriptions
    setattr(client._session, http_method, AsyncMock(side_effect=runtime_error))

    with pytest.raises(expected_exception) as exc_info:
        await call(client)

    assert type(exc_info.value) is expected_exception


async def test_fresh_session_renews_expired_token(client, mocked_responses, base_url):
    client._token_expiration = 0
    mock_list_subscriptions(mocked_responses, base_url, [])

    await client.list_subscriptions()

    assert client._session.headers["Authorization"] == "Bearer access_token"


@pytest.mark.parametrize(
    "tenant_id,expected_url",
    [
        pytest.param("my-tenant", "https://login.microsoftonline.com/my-tenant", id="tenant_id"),
        pytest.param(None, "https://login.microsoftonline.com/common", id="no_tenant_id"),
    ],
)
def test_normalize_office365_url(tenant_id, expected_url):
    client = SimpleNamespace(tenant_id=tenant_id)

    assert Office365API._normalize_office365_url(client) == expected_url  # type: ignore[arg-type]
