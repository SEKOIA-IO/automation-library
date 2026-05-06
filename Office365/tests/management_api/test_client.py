import re
from datetime import datetime, timedelta
from urllib.parse import urlencode

import orjson
import pytest
from aioresponses import aioresponses

from office365.management_api.errors import (
    ApplicationAuthenticationFailed,
    FailedToActivateO365Subscription,
    FailedToGetO365AuditContent,
    FailedToGetO365SubscriptionContents,
    FailedToListO365Subscriptions,
)
from office365.management_api.office365_client import Office365API


@pytest.fixture
def mocked_responses():
    with aioresponses() as m:
        yield m


@pytest.mark.asyncio
async def test_active_subscription_should_succeed(mocked_responses, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"

    for content_type in {"Audit.AzureActiveDirectory", "Audit.SharePoint", "Audit.General", "Audit.Exchange"}:
        mocked_responses.post(
            f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/start?contentType={content_type}",
            status=200,
            body=orjson.dumps(
                {
                    "contentType": content_type,
                    "status": "enabled",
                    "webhook": {
                        "status": "enabled",
                        "address": "https://webhook.myapp.com/o365/",
                        "authId": "o365activityapinotification",
                        "expiration": None,
                    },
                }
            ),
        )

    mocked_responses.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list",
        status=200,
        body="[]",
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    await client.activate_subscriptions()

    # finalize
    await client.close()


@pytest.mark.asyncio
async def test_office_365_auth_fail_no_token(mocked_responses, mock_azure_authentication_no_access_token, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"

    mocked_responses.post(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/start",
        status=200,
        body=orjson.dumps(
            {
                "contentType": "Audit.SharePoint",
                "status": "enabled",
                "webhook": {
                    "status": "enabled",
                    "address": "https://webhook.myapp.com/o365/",
                    "authId": "o365activityapinotification",
                    "expiration": None,
                },
            }
        ),
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(ApplicationAuthenticationFailed, match="Failed to get access token"):
        await client.activate_subscriptions()

    # finalize
    await client.close()


@pytest.mark.asyncio
async def test_office_365_auth_fail_bad_token(mocked_responses, mock_azure_authentication_wrong_token_type, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"

    mocked_responses.post(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/start",
        status=200,
        body=orjson.dumps(
            {
                "contentType": "Audit.SharePoint",
                "status": "enabled",
                "webhook": {
                    "status": "enabled",
                    "address": "https://webhook.myapp.com/o365/",
                    "authId": "o365activityapinotification",
                    "expiration": None,
                },
            }
        ),
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(ApplicationAuthenticationFailed, match="Bearer Authentication not supported"):
        await client.activate_subscriptions()

    # finalize
    await client.close()


@pytest.mark.asyncio
async def test_list_subscriptions(mocked_responses, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"

    mocked_responses.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list",
        status=200,
        body=orjson.dumps(
            [
                {
                    "contentType": "Audit.SharePoint",
                    "status": "enabled",
                    "webhook": {
                        "status": "enabled",
                        "address": "https://webhook.myapp.com/o365/",
                        "authId": "o365activityapinotification",
                        "expiration": None,
                    },
                }
            ]
        ),
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    assert await client.list_subscriptions() == ["Audit.SharePoint"]

    # finalize
    await client.close()


@pytest.mark.asyncio
async def test_get_subscription_contents(mocked_responses, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"

    mocked_responses.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/content",
        status=200,
        body=orjson.dumps(
            [
                {
                    "contentType": "Audit.SharePoint",
                    "contentId": "492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed\
89c62e6039ab833b$04",
                    "contentUri": "https://manage.office.com/api/v1.0/f28ab78a-d401-4060-8012-736e373933eb/activity/feed/\
audit/492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed89c62e6039ab833b$04",
                    "contentCreated": (datetime.now() - timedelta(hours=12)).isoformat("T"),
                    "contentExpiration": (datetime.now() + timedelta(hours=12)).isoformat("T"),
                },
            ]
        ),
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    client.get_subscription_contents(
        content_type="Audit.SharePoint", start_time=datetime.now() - timedelta(days=1), end_time=datetime.now()
    )

    # finalize
    await client.close()


@pytest.mark.asyncio
async def test_get_content(mocked_responses, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"

    mocked_responses.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list",
        status=200,
        body=orjson.dumps(
            [
                {
                    "contentType": "Audit.SharePoint",
                    "status": "enabled",
                    "webhook": {
                        "status": "enabled",
                        "address": "https://webhook.myapp.com/o365/",
                        "authId": "o365activityapinotification",
                        "expiration": None,
                    },
                }
            ]
        ),
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    assert await client.list_subscriptions() == ["Audit.SharePoint"]

    # finalize
    await client.close()


@pytest.mark.asyncio
async def test_activate_subscription_should_exception_when_handling_business_error(
    mocked_responses, mock_azure_authentication, tenant_id
):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    content_types = {"Audit.SharePoint"}

    for content_type in {
        "Audit.AzureActiveDirectory",
        "Audit.SharePoint",
        "Audit.General",
        "Audit.Exchange",
    } - content_types:
        mocked_responses.post(
            f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/start?contentType={content_type}",
            status=200,
            body="{}",
        )
    for content_type in content_types:
        mocked_responses.post(
            f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/start?contentType={content_type}",
            status=200,
            body='{"error": {"code": "error_code", "message": "error message"}}',
        )
    mocked_responses.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list",
        status=200,
        body="[]",
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(FailedToActivateO365Subscription):
        await client.activate_subscriptions()

    # finalize
    await client.close()


@pytest.mark.asyncio
async def test_activate_subscription_should_exception_on_http_error(
    mocked_responses, mock_azure_authentication, tenant_id
):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    content_types = {"Audit.SharePoint"}

    for content_type in {
        "Audit.AzureActiveDirectory",
        "Audit.SharePoint",
        "Audit.General",
        "Audit.Exchange",
    } - content_types:
        mocked_responses.post(
            f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/start?contentType={content_type}",
            status=200,
            body="{}",
        )
    for content_type in content_types:
        mocked_responses.post(
            f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/start?contentType={content_type}",
            status=400,
        )
    mocked_responses.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list",
        status=200,
        body="[]",
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(FailedToActivateO365Subscription):
        await client.activate_subscriptions()

    # finalize
    await client.close()


@pytest.mark.asyncio
async def test_list_subscriptions_should_succeed(mocked_responses, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"

    mocked_responses.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list",
        status=200,
        body=orjson.dumps(
            [
                {
                    "contentType": "Audit.SharePoint",
                    "status": "enabled",
                    "webhook": {
                        "status": "enabled",
                        "address": "https://webhook.myapp.com/o365/",
                        "authId": "o365activityapinotification",
                        "expiration": None,
                    },
                }
            ]
        ),
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    subscriptions = await client.list_subscriptions()

    # assert
    assert subscriptions is not None

    # finalize
    await client.close()


@pytest.mark.asyncio
async def test_list_subscriptions_should_exception_when_handling_business_error(
    mocked_responses, mock_azure_authentication, tenant_id
):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"

    mocked_responses.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list",
        status=200,
        body='{"error": {"code": "error_code", "message": "error message"}}',
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(FailedToListO365Subscriptions):
        await client.list_subscriptions()

    # finalize
    await client.close()


@pytest.mark.asyncio
async def test_list_subscriptions_should_exception_on_http_error(
    mocked_responses, mock_azure_authentication, tenant_id
):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"

    mocked_responses.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list",
        status=400,
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(FailedToListO365Subscriptions):
        await client.list_subscriptions()

    # finalize
    await client.close()


@pytest.mark.asyncio
async def test_get_subscription_contents_should_succeed(mocked_responses, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    content_type = "Audit.SharePoint"

    start_time = datetime.now() - timedelta(days=7)
    end_time = datetime.now()

    # flake8: noqa
    url = re.compile(
        f"https://manage\\.office\\.com/api/v1\\.0/{tenant_id}/activity/feed/subscriptions/content\\?contentType={content_type}"
    )
    mocked_responses.get(
        url,
        status=200,
        body=orjson.dumps(
            [
                {
                    "contentType": "Audit.SharePoint",
                    "contentId": "492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed\
89c62e6039ab833b$04",
                    "contentUri": "https://manage.office.com/api/v1.0/f28ab78a-d401-4060-8012-736e373933eb/activity/feed/\
audit/492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed89c62e6039ab833b$04",
                    "contentCreated": "2015-05-23T17:35:00.000Z",
                    "contentExpiration": "2015-05-30T17:35:00.000Z",
                },
                {
                    "contentType": "Audit.SharePoint",
                    "contentId": "492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc\
4aed89c62e6039ab833b$05",
                    "contentUri": "https://manage.office.com/api/v1.0/f28ab78a-d401-4060-8012-736e373933eb/activity/feed/\
audit/492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed89c62e6039ab833b$05",
                    "contentCreated": "2015-05-23T17:35:00.000Z",
                    "contentExpiration": "2015-05-30T17:35:00.000Z",
                },
            ]
        ),
    )
    # flake8: qa

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    gen = client.get_subscription_contents(content_type, start_time, end_time)

    # assert
    contents = await anext(gen)
    assert 2 == len(contents)
    query_string = urlencode(
        {"contentType": content_type, "endTime": end_time.isoformat("T"), "startTime": start_time.isoformat("T")}
    )
    url = f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/content?{query_string}"
    mocked_responses.assert_called_with(url, headers={"Authorization": "Bearer access_token"})
    with pytest.raises(StopAsyncIteration):
        await anext(gen)

    # finalize
    await client.close()


@pytest.mark.asyncio
async def test_get_subscription_contents_with_pagination_should_succeed(
    mocked_responses, mock_azure_authentication, tenant_id
):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    content_type = "Audit.SharePoint"

    # flake8: noqa
    mocked_responses.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/content?contentType={content_type}",
        status=200,
        body=orjson.dumps(
            [
                {
                    "contentType": "Audit.SharePoint",
                    "contentId": "492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed\
89c62e6039ab833b$04",
                    "contentUri": "https://manage.office.com/api/v1.0/f28ab78a-d401-4060-8012-736e373933eb/activity/feed/\
audit/492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed89c62e6039ab833b$04",
                    "contentCreated": "2015-05-23T17:35:00.000Z",
                    "contentExpiration": "2015-05-30T17:35:00.000Z",
                },
                {
                    "contentType": "Audit.SharePoint",
                    "contentId": "492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc\
4aed89c62e6039ab833b$05",
                    "contentUri": "https://manage.office.com/api/v1.0/f28ab78a-d401-4060-8012-736e373933eb/activity/feed/\
audit/492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed89c62e6039ab833b$05",
                    "contentCreated": "2015-05-23T17:35:00.000Z",
                    "contentExpiration": "2015-05-30T17:35:00.000Z",
                },
            ]
        ),
        headers={"NextPageUri": f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/content\
?contentType=content_types&nextPage=2015101900R022885001761"},
    )
    mocked_responses.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/content?contentType=content_types&nextPage=2015101900R022885001761",
        status=200,
        body=orjson.dumps(
            [
                {
                    "contentType": "Audit.SharePoint",
                    "contentId": "492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc\
4aed89c62e6039ab833b$06",
                    "contentUri": "https://manage.office.com/api/v1.0/f28ab78a-d401-4060-8012-736e373933eb/activity/feed/\
audit/492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed89c62e6039ab833b$06",
                    "contentCreated": "2015-05-23T17:35:00.000Z",
                    "contentExpiration": "2015-05-30T17:35:00.000Z",
                },
            ]
        ),
    )
    # flake8: qa

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    gen = client.get_subscription_contents(content_type)

    # assert
    pages = [item async for item in gen]
    assert 2 == len(pages)

    # finalize
    await client.close()


@pytest.mark.asyncio
async def test_get_subscription_contents_should_exception_when_handling_business_error(
    mocked_responses, mock_azure_authentication, tenant_id
):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    content_type = "Audit.SharePoint"

    # flake8: noqa
    mocked_responses.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/content?\
contentType={content_type}",
        status=200,
        body='{"error": {"code": "error_code", "message": "error message"}}',
    )
    # flake8: qa

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(FailedToGetO365SubscriptionContents):
        gen = client.get_subscription_contents(content_type)
        await anext(gen)

    # finalize
    await client.close()


@pytest.mark.asyncio
async def test_get_subscription_contents_should_exception_on_http_error(
    mocked_responses, mock_azure_authentication, tenant_id
):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    content_type = "Audit.SharePoint"
    # flake8: noqa
    mocked_responses.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/content?\
contentType={content_type}",
        status=400,
    )
    # flake8: qa

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(FailedToGetO365SubscriptionContents):
        gen = client.get_subscription_contents(content_type)
        await anext(gen)

    # finalize
    await client.close()


@pytest.mark.asyncio
async def test_get_content_should_succeed(mocked_responses, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    # flake8: noqa
    content_uri = "https://manage.office.com/api/v1.0/f28ab78a-d401-4060-8012-736e373933eb/activity/feed/\
audit/492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed89c62e6039ab833b$04"
    # flake8: qa

    mocked_responses.get(
        content_uri,
        status=200,
        body=orjson.dumps(
            [
                {
                    "CreationTime": "2015-06-29T20:03:19",
                    "Id": "80c76bd2-9d81-4c57-a97a-accfc3443dca",
                    "Operation": "PasswordLogonInitialAuthUsingPassword",
                    "OrganizationId": "41463f53-8812-40f4-890f-865bf6e35190",
                    "RecordType": 9,
                    "ResultStatus": "failed",
                    "UserKey": "1153977025279851686@contoso.onmicrosoft.com",
                    "UserType": 0,
                    "Workload": "AzureActiveDirectory",
                    "ClientIP": "134.170.188.221",
                    "ObjectId": "admin@contoso.onmicrosoft.com",
                    "UserId": "admin@contoso.onmicrosoft.com",
                    "AzureActiveDirectoryEventType": 0,
                    "ExtendedProperties": [
                        {
                            "Name": "LoginError",
                            "Value": "-2147217390;PP_E_BAD_PASSWORD;The entered and stored passwords do not match.",
                        }
                    ],
                    "Client": "Exchange",
                    "LoginStatus": -2147217390,
                    "UserDomain": "contoso.onmicrosoft.com",
                },
                {
                    "CreationTime": "2015-06-29T20:03:34",
                    "Id": "4e655d3f-35fa-42e0-b050-264b2d255c7a",
                    "Operation": "PasswordLogonInitialAuthUsingPassword",
                    "OrganizationId": "41463f53-8812-40f4-890f-865bf6e35190",
                    "RecordType": 9,
                    "ResultStatus": "success",
                    "UserKey": "1153977025279851686@contoso.onmicrosoft.com",
                    "UserType": 0,
                    "Workload": "AzureActiveDirectory",
                    "ClientIP": "134.170.188.221",
                    "ObjectId": "admin@contoso.onmicrosoft.com",
                    "UserId": "admin@contoso.onmicrosoft.com",
                    "AzureActiveDirectoryEventType": 0,
                    "Client": "Exchange",
                    "LoginStatus": 0,
                    "UserDomain": "contoso.onmicrosoft.com",
                },
            ]
        ),
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    content = await client.get_content(content_uri)

    # assert
    assert 2 == len(content)

    # finalize
    await client.close()


@pytest.mark.asyncio
async def test_get_content_should_exception_when_handling_business_error(
    mocked_responses, mock_azure_authentication, tenant_id
):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    # flake8: noqa
    content_uri = "https://manage.office.com/api/v1.0/f28ab78a-d401-4060-8012-736e373933eb/activity/feed/\
audit/492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed89c62e6039ab833b$04"
    # flake8: qa

    mocked_responses.get(content_uri, status=200, body='{"error": {"code": "error_code", "message": "error message"}}')

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(FailedToGetO365AuditContent):
        await client.get_content(content_uri)

    # finalize
    await client.close()


@pytest.mark.asyncio
async def test_get_content_should_exception_on_http_error(mocked_responses, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    # flake8: noqa
    content_uri = "https://manage.office.com/api/v1.0/f28ab78a-d401-4060-8012-736e373933eb/activity/feed/\
audit/492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed89c62e6039ab833b$04"
    # flake8: qa

    mocked_responses.get(
        content_uri,
        status=400,
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(FailedToGetO365AuditContent):
        await client.get_content(content_uri)

    # finalize
    await client.close()


@pytest.fixture
def patch_async_sleep():
    """Patch asyncio.sleep used by office365_client to a no-op for fast tests."""
    from unittest.mock import patch

    async def _noop(_seconds):
        return None

    with patch("office365.management_api.office365_client.asyncio.sleep", side_effect=_noop) as mock:
        yield mock


@pytest.mark.asyncio
async def test_list_subscriptions_retries_on_5xx_then_succeeds(
    mocked_responses, mock_azure_authentication, tenant_id, patch_async_sleep
):
    list_url = f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list"
    # First two attempts return 503, third succeeds.
    mocked_responses.get(list_url, status=503, body="busy")
    mocked_responses.get(list_url, status=503, body="still busy")
    mocked_responses.get(
        list_url, status=200, body=orjson.dumps([{"contentType": "Audit.SharePoint", "status": "enabled"}])
    )

    client = Office365API(client_id="cid", client_secret="cs", tenant_id=tenant_id)

    result = await client.list_subscriptions()

    assert result == ["Audit.SharePoint"]
    assert patch_async_sleep.call_count == 2
    await client.close()


@pytest.mark.asyncio
async def test_list_subscriptions_retries_on_429_with_retry_after(
    mocked_responses, mock_azure_authentication, tenant_id, patch_async_sleep
):
    list_url = f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list"
    mocked_responses.get(list_url, status=429, headers={"Retry-After": "2"}, body="throttled")
    mocked_responses.get(
        list_url, status=200, body=orjson.dumps([{"contentType": "Audit.SharePoint", "status": "enabled"}])
    )

    client = Office365API(client_id="cid", client_secret="cs", tenant_id=tenant_id)

    result = await client.list_subscriptions()

    assert result == ["Audit.SharePoint"]
    # First sleep should reflect the Retry-After value.
    assert patch_async_sleep.call_args_list[0].args[0] == 2.0
    await client.close()


@pytest.mark.asyncio
async def test_list_subscriptions_gives_up_after_max_attempts(
    mocked_responses, mock_azure_authentication, tenant_id, patch_async_sleep
):
    list_url = f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list"
    long_html = "<html>" + ("a" * 5000) + "</html>"
    for _ in range(5):
        mocked_responses.get(list_url, status=503, body=long_html)

    client = Office365API(client_id="cid", client_secret="cs", tenant_id=tenant_id)

    with pytest.raises(FailedToListO365Subscriptions) as exc_info:
        await client.list_subscriptions()

    assert exc_info.value.context.get("status_code") == 503
    body = exc_info.value.context.get("body", "")
    assert "(truncated)" in body
    assert len(body) <= 250
    await client.close()


@pytest.mark.asyncio
async def test_list_subscriptions_does_not_retry_on_4xx(
    mocked_responses, mock_azure_authentication, tenant_id, patch_async_sleep
):
    list_url = f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list"
    # Only register a single 401 — if the client retries, aioresponses raises (no mock for the second call).
    mocked_responses.get(list_url, status=401, body="unauthorized")

    client = Office365API(client_id="cid", client_secret="cs", tenant_id=tenant_id)

    with pytest.raises(FailedToListO365Subscriptions) as exc_info:
        await client.list_subscriptions()

    assert exc_info.value.context.get("status_code") == 401
    # No retry sleeps should have been called for a 4xx.
    assert patch_async_sleep.call_count == 0
    await client.close()


@pytest.mark.asyncio
async def test_get_content_extracts_error_code_from_json_body(
    mocked_responses, mock_azure_authentication, tenant_id, patch_async_sleep
):
    content_uri = (
        "https://manage.office.com/api/v1.0/f28ab78a-d401-4060-8012-736e373933eb/"
        "activity/feed/audit/4a81a7c326fc4aed89c62e6039ab833b"
    )
    mocked_responses.get(
        content_uri,
        status=500,
        body='{"error": {"code": "AF50005", "message": "An internal error occurred. Retry the request."}}',
    )
    # Subsequent retries also fail to confirm we exhaust retries with the same body shape.
    for _ in range(4):
        mocked_responses.get(
            content_uri,
            status=500,
            body='{"error": {"code": "AF50005", "message": "An internal error occurred. Retry the request."}}',
        )

    client = Office365API(client_id="cid", client_secret="cs", tenant_id=tenant_id)

    with pytest.raises(FailedToGetO365AuditContent) as exc_info:
        await client.get_content(content_uri)

    assert exc_info.value.context.get("status_code") == 500
    assert exc_info.value.context.get("error_code") == "AF50005"
    assert "Retry the request" in exc_info.value.context.get("error_message", "")
    await client.close()
