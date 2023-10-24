from datetime import datetime, timedelta
import pytest

import requests_mock
from office365.management_api.errors import (
    ApplicationAuthenticationFailed,
    FailedToActivateO365Subscription,
    FailedToGetO365AuditContent,
    FailedToGetO365SubscriptionContents,
    FailedToListO365Subscriptions,
)

from office365.management_api.office365_client import Office365API


def test_active_subscription_should_succeed(requests_mock, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    content_types = {"Audit.SharePoint"}

    requests_mock.post(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/start",
        status_code=200,
        json={
            "contentType": "Audit.SharePoint",
            "status": "enabled",
            "webhook": {
                "status": "enabled",
                "address": "https://webhook.myapp.com/o365/",
                "authId": "o365activityapinotification",
                "expiration": None,
            },
        },
    )
    requests_mock.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list",
        status_code=200,
        json=[],
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    assert client.activate_subscriptions(content_types)


def test_office_365_auth_fail_no_token(requests_mock, mock_azure_authentication_no_access_token, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    content_types = {"Audit.SharePoint"}

    requests_mock.post(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/start",
        status_code=200,
        json={
            "contentType": "Audit.SharePoint",
            "status": "enabled",
            "webhook": {
                "status": "enabled",
                "address": "https://webhook.myapp.com/o365/",
                "authId": "o365activityapinotification",
                "expiration": None,
            },
        },
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(ApplicationAuthenticationFailed, match="Failed to get access token"):
        client.activate_subscriptions(content_types)


def test_office_365_auth_fail_bad_token(requests_mock, mock_azure_authentication_wrong_token_type, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    content_types = {"Audit.SharePoint"}

    requests_mock.post(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/start",
        status_code=200,
        json={
            "contentType": "Audit.SharePoint",
            "status": "enabled",
            "webhook": {
                "status": "enabled",
                "address": "https://webhook.myapp.com/o365/",
                "authId": "o365activityapinotification",
                "expiration": None,
            },
        },
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(ApplicationAuthenticationFailed, match="Bearer Authentication not supported"):
        client.activate_subscriptions(content_types)


def test_list_subscriptions(requests_mock, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"

    requests_mock.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list",
        status_code=200,
        json=[
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
        ],
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    assert client.list_subscriptions() == ["Audit.SharePoint"]


def test_get_subscription_contents(requests_mock, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"

    requests_mock.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/content",
        status_code=200,
        json=[
            {
                "contentType": "Audit.SharePoint",
                "contentId": "492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed\
89c62e6039ab833b$04",
                "contentUri": "https://manage.office.com/api/v1.0/f28ab78a-d401-4060-8012-736e373933eb/activity/feed/\
audit/492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed89c62e6039ab833b$04",
                "contentCreated": (datetime.now() - timedelta(hours=12)).isoformat("T"),
                "contentExpiration": (datetime.now() + timedelta(hours=12)).isoformat("T"),
            },
        ],
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


def test_get_content(requests_mock, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"

    requests_mock.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list",
        status_code=200,
        json=[
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
        ],
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    assert client.list_subscriptions() == ["Audit.SharePoint"]


def test_activate_subscription_should_exception_when_handling_business_error(
    requests_mock, mock_azure_authentication, tenant_id
):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    content_types = {"Audit.SharePoint"}

    requests_mock.post(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/start",
        status_code=200,
        json={"error": {"code": "error_code", "message": "error message"}},
    )
    requests_mock.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list",
        status_code=200,
        json=[],
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(FailedToActivateO365Subscription):
        client.activate_subscriptions(content_types)


def test_activate_subscription_should_exception_on_http_error(requests_mock, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    content_types = {"Audit.SharePoint"}

    requests_mock.post(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/start",
        status_code=400,
    )
    requests_mock.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list",
        status_code=200,
        json=[],
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(FailedToActivateO365Subscription):
        client.activate_subscriptions(content_types)


def test_list_subscriptions_should_succeed(requests_mock, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"

    requests_mock.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list",
        status_code=200,
        json=[
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
        ],
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    subscriptions = client.list_subscriptions()

    # assert
    assert subscriptions is not None


def test_list_subscriptions_should_exception_when_handling_business_error(
    requests_mock, mock_azure_authentication, tenant_id
):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"

    requests_mock.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list",
        status_code=200,
        json={"error": {"code": "error_code", "message": "error message"}},
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(FailedToListO365Subscriptions):
        client.list_subscriptions()


def test_list_subscriptions_should_exception_on_http_error(requests_mock, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"

    requests_mock.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list",
        status_code=400,
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(FailedToListO365Subscriptions):
        client.list_subscriptions()


def test_get_subscription_contents_should_succeed(requests_mock, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    content_type = "Audit.SharePoint"

    start_time = datetime.now() - timedelta(days=7)
    end_time = datetime.now()

    # flake8: noqa
    requests_mock.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/content?\
contentType={content_type}",
        status_code=200,
        json=[
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
        ],
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
    contents = next(gen)
    assert 2 == len(contents)
    assert datetime.fromisoformat(requests_mock.last_request.qs["starttime"][0]) == start_time
    assert datetime.fromisoformat(requests_mock.last_request.qs["endtime"][0]) == end_time
    with pytest.raises(StopIteration):
        next(gen)


def test_get_subscription_contents_with_pagination_should_succeed(requests_mock, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    content_type = "Audit.SharePoint"

    # flake8: noqa
    requests_mock.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/content?\
contentType={content_type}",
        status_code=200,
        json=[
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
        ],
        headers={
            "NextPageUri": f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/content\
?contentType=content_types&nextPage=2015101900R022885001761"
        },
    )
    requests_mock.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/content?contentType=content_types\
&nextPage=2015101900R022885001761",
        status_code=200,
        json=[
            {
                "contentType": "Audit.SharePoint",
                "contentId": "492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc\
4aed89c62e6039ab833b$06",
                "contentUri": "https://manage.office.com/api/v1.0/f28ab78a-d401-4060-8012-736e373933eb/activity/feed/\
audit/492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed89c62e6039ab833b$06",
                "contentCreated": "2015-05-23T17:35:00.000Z",
                "contentExpiration": "2015-05-30T17:35:00.000Z",
            },
        ],
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
    pages = list(gen)
    assert 2 == len(pages)


def test_get_subscription_contents_should_exception_when_handling_business_error(
    requests_mock, mock_azure_authentication, tenant_id
):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    content_type = "Audit.SharePoint"

    # flake8: noqa
    requests_mock.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/content?\
contentType={content_type}",
        status_code=200,
        json={"error": {"code": "error_code", "message": "error message"}},
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
        next(gen)


def test_get_subscription_contents_should_exception_on_http_error(requests_mock, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    content_type = "Audit.SharePoint"

    # flake8: noqa
    requests_mock.get(
        f"https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/content?\
contentType={content_type}",
        status_code=400,
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
        next(gen)


def test_get_content_should_succeed(requests_mock, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    # flake8: noqa
    content_uri = "https://manage.office.com/api/v1.0/f28ab78a-d401-4060-8012-736e373933eb/activity/feed/\
audit/492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed89c62e6039ab833b$04"
    # flake8: qa

    requests_mock.get(
        content_uri,
        status_code=200,
        json=[
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
        ],
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    content = client.get_content(content_uri)

    # assert
    assert 2 == len(content)


def test_get_content_should_exception_when_handling_business_error(
    requests_mock, mock_azure_authentication, tenant_id
):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    # flake8: noqa
    content_uri = "https://manage.office.com/api/v1.0/f28ab78a-d401-4060-8012-736e373933eb/activity/feed/\
audit/492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed89c62e6039ab833b$04"
    # flake8: qa

    requests_mock.get(content_uri, status_code=200, json={"error": {"code": "error_code", "message": "error message"}})

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(FailedToGetO365AuditContent):
        client.get_content(content_uri)


def test_get_content_should_exception_on_http_error(requests_mock, mock_azure_authentication, tenant_id):
    # arrange
    client_id = "client_id"
    client_secret = "client_secret"
    # flake8: noqa
    content_uri = "https://manage.office.com/api/v1.0/f28ab78a-d401-4060-8012-736e373933eb/activity/feed/\
audit/492638008028$492638008028$f28ab78ad40140608012736e373933ebspo2015043022$4a81a7c326fc4aed89c62e6039ab833b$04"
    # flake8: qa

    requests_mock.get(
        content_uri,
        status_code=400,
    )

    client = Office365API(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )

    # act
    with pytest.raises(FailedToGetO365AuditContent):
        client.get_content(content_uri)
