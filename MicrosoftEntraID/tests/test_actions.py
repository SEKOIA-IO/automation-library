import json
from typing import Type, Any, Optional
from unittest.mock import AsyncMock, patch

import pytest
import requests
from kiota_abstractions.request_adapter import RequestAdapter
from msgraph import GraphServiceClient

from azure_ad.base import AzureADModule, MicrosoftGraphAction
from azure_ad.delete_app import DeleteApplicationAction
from azure_ad.get_sign_ins import GetSignInsAction, RevokeSignInsSessionsAction
from azure_ad.get_user_authentication_methods import GetUserAuthenticationMethodsAction
from azure_ad.user import DisableUserAction, EnableUserAction, GetUserAction, ResetUserPasswordAction


def configured_action(action: Type[MicrosoftGraphAction]):
    module = AzureADModule()
    a = action(module)

    a.module.configuration = {
        "tenant_id": "azefazefazegazetazeytazeyaze",
        "client_id": "e139c076-122f-4c2e-9d0d-azefazegazeg",
        "client_secret": "client_secret",
        "username": "username",
        "password": "password",
    }

    return a


class TestRequestAdapter(RequestAdapter):
    def __init__(self, send_async: Optional[requests.Response] = None):
        self._send_async = send_async

    def get_serialization_writer_factory(self) -> Any:
        pass

    async def send_collection_async(self, request_info: Any, parsable_factory: Any, error_map: Any) -> Any:
        pass

    async def send_collection_of_primitive_async(self, request_info: Any, response_type: Any, error_map: Any) -> Any:
        pass

    async def send_primitive_async(self, request_info: Any, response_type: str, error_map: Any) -> Any:
        pass

    async def send_no_response_content_async(self, request_info: Any, error_map: Any) -> Any:
        pass

    def enable_backing_store(self, backing_store_factory: Any) -> Any:
        pass

    async def convert_to_native_async(self, request_info: Any) -> Any:
        pass

    async def send_async(self, request_info: Any, parsable_factory: Any, error_map: Any) -> Any:
        return self._send_async


@pytest.mark.asyncio
async def test_get_user():
    action = configured_action(GetUserAction)
    expected_user = {
        "id": "31c888e1-54d7-4cd5-86d5-a6fc32f397e7",
        "accountEnabled": True,
        "city": None,
        "companyName": None,
        "country": None,
        "createdDateTime": "2022-02-01T15:44:02Z",
        "creationType": None,
        "deletedDateTime": None,
        "department": None,
        "displayName": "Jean Test",
        "jobTitle": None,
        "lastPasswordChangeDateTime": "2022-02-04T14:08:49Z",
        "mail": None,
        "mobilePhone": None,
        "assignedLicenses": [{"disabledPlans": [], "skuId": "b05e124f-c7cc-45a0-a6aa-8cf78c946968"}],
        "identities": [
            {
                "signInType": "userPrincipalName",
                "issuer": "test.onmicrosoft.com",
                "issuerAssignedId": "jean.test@test.onmicrosoft.com",
            }
        ],
        "userPrincipalName": "jean.test@test.onmicrosoft.com",
    }

    response = requests.Response()
    response._content = json.dumps(expected_user).encode("utf-8")
    response.status_code = 200

    async_mock = AsyncMock(return_value=response)
    with patch("azure_ad.user.GetUserAction.query_get_user", side_effect=async_mock):
        results = await action.run({"userPrincipalName": "jean.test@test.onmicrosoft.com"})

        assert results == expected_user


@pytest.mark.asyncio
async def test_get_user_1():
    action = configured_action(GetUserAction)
    expected_user = {
        "id": "31c888e1-54d7-4cd5-86d5-a6fc32f397e7",
        "accountEnabled": True,
        "city": None,
        "companyName": None,
        "country": None,
        "createdDateTime": "2022-02-01T15:44:02Z",
        "creationType": None,
        "deletedDateTime": None,
        "department": None,
        "displayName": "Jean Test",
        "jobTitle": None,
        "lastPasswordChangeDateTime": "2022-02-04T14:08:49Z",
        "mail": None,
        "mobilePhone": None,
        "assignedLicenses": [{"disabledPlans": [], "skuId": "b05e124f-c7cc-45a0-a6aa-8cf78c946968"}],
        "identities": [
            {
                "signInType": "userPrincipalName",
                "issuer": "test.onmicrosoft.com",
                "issuerAssignedId": "jean.test@test.onmicrosoft.com",
            }
        ],
        "userPrincipalName": "jean.test@test.onmicrosoft.com",
    }

    response = requests.Response()
    response._content = json.dumps(expected_user).encode("utf-8")
    response.status_code = 200

    mocked_adapter = TestRequestAdapter(send_async=response)
    graph_client = GraphServiceClient(request_adapter=mocked_adapter)
    action._client = graph_client

    results = await action.run({"userPrincipalName": "jean.test@test.onmicrosoft.com"})
    assert results == expected_user


@pytest.mark.asyncio
async def test_disable_user():
    action = configured_action(DisableUserAction)

    response = requests.Response()
    response._content = b'{"accountEnabled": False}'
    response.status_code = 204

    async_mock = AsyncMock(return_value=response)
    with patch("azure_ad.user.DisableUserAction.query_disable_user", side_effect=async_mock):
        results = await action.run({"userPrincipalName": "jean.test@test.onmicrosoft.com"})

        assert results is None


@pytest.mark.asyncio
async def test_enable_user():
    action = configured_action(EnableUserAction)

    response = requests.Response()
    response._content = b'{"accountEnabled": True}'
    response.status_code = 204

    async_mock = AsyncMock(return_value=response)
    with patch("azure_ad.user.EnableUserAction.query_enable_user", side_effect=async_mock):
        results = await action.run({"userPrincipalName": "jean.test@test.onmicrosoft.com"})

        assert results is None


@pytest.mark.asyncio
async def test_reset_user_password():
    action = configured_action(ResetUserPasswordAction)

    methods_response, reset_response = requests.Response(), requests.Response()
    expected_methods_response = {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('')/authentication/passwordMethods",
        "value": [{"id": "28c10230-6103-485e-b985-444c60001490", "password": "", "createdDateTime": ""}],
    }
    methods_response._content = json.dumps(expected_methods_response).encode("utf-8")
    methods_response.status_code = 200
    methods_async_mock = AsyncMock(return_value=methods_response)

    reset_response._content = b"{}"
    reset_response.status_code = 202

    reset_async_mock = AsyncMock(return_value=reset_response)
    with patch("azure_ad.user.ResetUserPasswordAction.query_list_user_methods", side_effect=methods_async_mock):
        with patch("azure_ad.user.ResetUserPasswordAction.query_reset_user_password", side_effect=reset_async_mock):
            results = await action.run(
                {"userPrincipalName": "jean.test@test.onmicrosoft.com", "userNewPassword": "justtotest"}
            )

            assert results is None


@pytest.mark.asyncio
async def test_get_user_authentication_methods():
    action = configured_action(GetUserAuthenticationMethodsAction)

    expected = {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#reports/authenticationMethods/userRegistrationDetails",
        "value": [
            {
                "id": "31c888e1-54d7-4cd5-86d5-a6fc32f397e7",
                "userPrincipalName": "jean.test@test.onmicrosoft.com",
                "userDisplayName": "Jean Test",
                "isSsprRegistered": True,
                "isSsprEnabled": False,
                "isSsprCapable": False,
                "isMfaRegistered": True,
                "isMfaCapable": True,
                "isPasswordlessCapable": False,
                "methodsRegistered": ["mobilePhone", "windowsHelloForBusiness"],
                "defaultMfaMethod": "mobilePhone",
            }
        ],
    }
    value_expected = [
        {
            "id": "31c888e1-54d7-4cd5-86d5-a6fc32f397e7",
            "userPrincipalName": "jean.test@test.onmicrosoft.com",
            "userDisplayName": "Jean Test",
            "isSsprRegistered": True,
            "isSsprEnabled": False,
            "isSsprCapable": False,
            "isMfaRegistered": True,
            "isMfaCapable": True,
            "isPasswordlessCapable": False,
            "methodsRegistered": ["mobilePhone", "windowsHelloForBusiness"],
            "defaultMfaMethod": "mobilePhone",
        }
    ]

    final_value_expected = {"authenticationResults": value_expected}

    response = requests.Response()
    response._content = json.dumps(expected).encode("utf-8")
    response.status_code = 200

    async_mock = AsyncMock(return_value=response)
    with patch(
        "azure_ad.get_user_authentication_methods.GetUserAuthenticationMethodsAction.query_user_auth_methods",
        side_effect=async_mock,
    ):
        results = await action.run({"userPrincipalName": "jean.test@test.onmicrosoft.com"})

        assert results == final_value_expected


SIGN_INS: list[dict] = [
    {
        "id": "1c60ed7c-be49-4e52-b7ff-20ec6df96800",
        "createdDateTime": "2022-07-05T10:26:13Z",
        "userDisplayName": "John Doe",
        "userPrincipalName": "test@gmail.com",
        "userId": "b7873f1b-547b-4605-ad9e-abc76e92f902",
        "appId": "747b0e83-6618-41b8-9062-e7d1783f1223",
        "appDisplayName": "Azure Portal",
        "ipAddress": "1.2.3.4",
        "ipAddressFromResourceProvider": None,
        "clientAppUsed": "Browser",
        "userAgent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:101.0) Gecko/20100101 Firefox/101.0",
        "correlationId": "2bf6255a-33a8-4869-9ad4-0d135f7c2739",
        "conditionalAccessStatus": "notApplied",
        "originalRequestId": "",
        "isInteractive": True,
        "tokenIssuerName": "",
        "tokenIssuerType": "AzureAD",
        "clientCredentialType": "none",
        "processingTimeInMilliseconds": 395,
        "riskDetail": "none",
        "riskLevelAggregated": "none",
        "riskLevelDuringSignIn": "none",
        "riskState": "none",
        "riskEventTypes_v2": [],
        "resourceDisplayName": "Windows Azure Service Management API",
        "resourceId": "4f3fbf67-c4cf-4127-9444-08b0d4f1417b",
        "resourceTenantId": "61b97b01-53be-4f0f-a054-3988c23668dc",
        "homeTenantId": "61b97b01-53be-4f0f-a054-3988c23668dc",
        "homeTenantName": "",
        "authenticationMethodsUsed": [],
        "authenticationRequirement": "singleFactorAuthentication",
        "signInIdentifier": "",
        "signInIdentifierType": None,
        "servicePrincipalName": None,
        "signInEventTypes": ["interactiveUser"],
        "servicePrincipalId": "",
        "federatedCredentialId": None,
        "userType": "member",
        "flaggedForReview": False,
        "isTenantRestricted": False,
        "autonomousSystemNumber": 207215,
        "crossTenantAccessType": "b2bCollaboration",
        "servicePrincipalCredentialKeyId": None,
        "servicePrincipalCredentialThumbprint": "",
        "uniqueTokenIdentifier": "MWM2MGVkN2MtYmU0OS00ZTUyLWI3ZmYtMjBlYzZkZjk2ODAw",
        "incomingTokenType": "none",
        "authenticationProtocol": "none",
        "resourceServicePrincipalId": "b90864b4-19a4-49c5-a02c-74ad57e2e5f5",
        "status": {
            "errorCode": 0,
            "failureReason": "Other.",
            "additionalDetails": None,
        },
        "deviceDetail": {
            "deviceId": "",
            "displayName": "",
            "operatingSystem": "Linux",
            "browser": "Firefox 101.0",
            "isCompliant": False,
            "isManaged": False,
            "trustType": "",
        },
        "location": {
            "city": "Paris",
            "state": "Paris",
            "countryOrRegion": "FR",
            "geoCoordinates": {
                "altitude": None,
                "latitude": 48.86023,
                "longitude": 2.34107,
            },
        },
        "appliedConditionalAccessPolicies": [],
        "authenticationContextClassReferences": [],
        "authenticationProcessingDetails": [{"key": "Root Key Type", "value": "Unknown"}],
        "networkLocationDetails": [],
        "authenticationDetails": [
            {
                "authenticationStepDateTime": "2022-07-05T10:26:13Z",
                "authenticationMethod": "Previously satisfied",
                "authenticationMethodDetail": None,
                "succeeded": True,
                "authenticationStepResultDetail": "First factor requirement satisfied by claim in the token",
                "authenticationStepRequirement": "",
            }
        ],
        "authenticationRequirementPolicies": [],
        "sessionLifetimePolicies": [],
        "privateLinkDetails": {
            "policyId": "",
            "policyName": "",
            "resourceId": "",
            "policyTenantId": "",
        },
    },
    {
        "id": "fb013d56-f4a7-4df2-93a4-83869bfb4d00",
        "createdDateTime": "2022-07-04T15:44:18Z",
        "userDisplayName": "John Doe",
        "userPrincipalName": "test@gmail.com",
        "userId": "b7873f1b-547b-4605-ad9e-abc76e92f902",
        "appId": "747b0e83-6618-41b8-9062-e7d1783f1223",
        "appDisplayName": "Azure Portal",
        "ipAddress": "5.6.7.8",
        "ipAddressFromResourceProvider": None,
        "clientAppUsed": "Browser",
        "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36",  # noqa: E501
        "correlationId": "b93a3a34-31ae-4c00-a757-e59b5d2adc54",
        "conditionalAccessStatus": "notApplied",
        "originalRequestId": "",
        "isInteractive": True,
        "tokenIssuerName": "",
        "tokenIssuerType": "AzureAD",
        "clientCredentialType": "none",
        "processingTimeInMilliseconds": 326,
        "riskDetail": "none",
        "riskLevelAggregated": "none",
        "riskLevelDuringSignIn": "none",
        "riskState": "none",
        "riskEventTypes_v2": [],
        "resourceDisplayName": "Windows Azure Service Management API",
        "resourceId": "4f3fbf67-c4cf-4127-9444-08b0d4f1417b",
        "resourceTenantId": "61b97b01-53be-4f0f-a054-3988c23668dc",
        "homeTenantId": "61b97b01-53be-4f0f-a054-3988c23668dc",
        "homeTenantName": "",
        "authenticationMethodsUsed": [],
        "authenticationRequirement": "singleFactorAuthentication",
        "signInIdentifier": "",
        "signInIdentifierType": None,
        "servicePrincipalName": None,
        "signInEventTypes": ["interactiveUser"],
        "servicePrincipalId": "",
        "federatedCredentialId": None,
        "userType": "member",
        "flaggedForReview": False,
        "isTenantRestricted": False,
        "autonomousSystemNumber": 15557,
        "crossTenantAccessType": "b2bCollaboration",
        "servicePrincipalCredentialKeyId": None,
        "servicePrincipalCredentialThumbprint": "",
        "uniqueTokenIdentifier": "ZmIwMTNkNTYtZjRhNy00ZGYyLTkzYTQtODM4NjliZmI0ZDAw",
        "incomingTokenType": "none",
        "authenticationProtocol": "none",
        "resourceServicePrincipalId": "b90864b4-19a4-49c5-a02c-74ad57e2e5f5",
        "status": {
            "errorCode": 0,
            "failureReason": "Other.",
            "additionalDetails": None,
        },
        "deviceDetail": {
            "deviceId": "",
            "displayName": "",
            "operatingSystem": "Linux",
            "browser": "Chrome 103.0.0",
            "isCompliant": False,
            "isManaged": False,
            "trustType": "",
        },
        "location": {
            "city": "Paris",
            "state": "Paris",
            "countryOrRegion": "FR",
            "geoCoordinates": {
                "altitude": None,
                "latitude": 48.86023,
                "longitude": 2.34107,
            },
        },
        "appliedConditionalAccessPolicies": [],
        "authenticationContextClassReferences": [],
        "authenticationProcessingDetails": [
            {"key": "Login Hint Present", "value": "True"},
            {"key": "Root Key Type", "value": "Unknown"},
        ],
        "networkLocationDetails": [],
        "authenticationDetails": [
            {
                "authenticationStepDateTime": "2022-07-04T15:44:18Z",
                "authenticationMethod": "Previously satisfied",
                "authenticationMethodDetail": None,
                "succeeded": True,
                "authenticationStepResultDetail": "First factor requirement satisfied by claim in the token",
                "authenticationStepRequirement": "",
            }
        ],
        "authenticationRequirementPolicies": [],
        "sessionLifetimePolicies": [],
        "privateLinkDetails": {
            "policyId": "",
            "policyName": "",
            "resourceId": "",
            "policyTenantId": "",
        },
    },
]


@pytest.mark.asyncio
async def test_get_signins():
    action = configured_action(GetSignInsAction)

    expected = {"value": SIGN_INS}
    value_expected = {"signIns": SIGN_INS}
    response = requests.Response()
    response._content = json.dumps(expected).encode("utf-8")
    response.status_code = 200

    async_mock = AsyncMock(return_value=response)
    with patch("azure_ad.get_sign_ins.GetSignInsAction.query_get_user_signin", side_effect=async_mock):
        results = await action.run({"userPrincipalName": "jean.test@test.onmicrosoft.com"})

        assert results == value_expected


@pytest.mark.asyncio
async def test_revoke_signins():
    action = configured_action(RevokeSignInsSessionsAction)

    expected = {"@odata.context": "https://graph.microsoft.com/v1.0/$metadata#Edm.Boolean", "value": True}
    response = requests.Response()
    response._content = json.dumps(expected).encode("utf-8")
    response.status_code = 200

    async_mock = AsyncMock(return_value=response)
    with patch("azure_ad.get_sign_ins.RevokeSignInsSessionsAction.query_revoke_signin", side_effect=async_mock):
        results = await action.run({"userPrincipalName": "jean.test@test.onmicrosoft.com"})

        assert results is None


@pytest.mark.asyncio
async def test_delete_app():
    action = configured_action(DeleteApplicationAction)

    response = requests.Response()
    response._content = b"{}"
    response.status_code = 200

    async_mock = AsyncMock(return_value=response)
    with patch("azure_ad.delete_app.DeleteApplicationAction.query_delete_app", side_effect=async_mock):
        results = await action.run({"id": "1986123896DGAZ12938"})

        assert results is None
