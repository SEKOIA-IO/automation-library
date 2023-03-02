import requests_mock
from azure_ad.base import AzureADModule, MicrosoftGraphAction
from azure_ad.get_sign_ins import GetSignInsAction
from azure_ad.get_user_authentication_methods import GetUserAuthenticationMethodsAction
from azure_ad.user import DisableUserAction, EnableUserAction, GetUserAction


def configured_action(action: MicrosoftGraphAction):
    module = AzureADModule()
    a = action(module)

    a.module.configuration = {
        "tenant_id": "my-tenant-id",
        "client_id": "my-client-id",
        "client_secret": "my-client-secret",
    }

    return a


def test_get_user():
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

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/beta/users/jean.test@test.onmicrosoft.com?%24select=id%2CaccountEnabled%2CassignedLicenses%2Ccity%2CcompanyName%2Ccountry%2CcreatedDateTime%2CcreationType%2CdeletedDateTime%2Cdepartment%2CdisplayName%2Cidentities%2CjobTitle%2ClastPasswordChangeDateTime%2Cmail%2CmobilePhone%2CuserPrincipalName",  # noqa: E501
            json=expected_user,
        )
        results = action.run({"userPrincipalName": "jean.test@test.onmicrosoft.com"})

    assert results == expected_user


def test_get_user_authentication_methods():
    action = configured_action(GetUserAuthenticationMethodsAction)

    expected = {
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

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/beta/reports/authenticationMethods/userRegistrationDetails/?%24filter=userPrincipalName+eq+%27jean.test%40test.onmicrosoft.com%27",  # noqa: E501
            json={"value": [expected]},
        )
        results = action.run({"userPrincipalName": "jean.test@test.onmicrosoft.com"})

    assert results == expected


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


def test_get_signins():
    action = configured_action(GetSignInsAction)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/beta/auditLogs/signIns",
            json={"value": SIGN_INS},
            complete_qs=True,
        )
        results = action.run({})

    assert results == {"signIns": SIGN_INS}


def test_get_signins_specific_user():
    action = configured_action(GetSignInsAction)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/beta/auditLogs/signIns?%24filter=userPrincipalName+eq+%27test%40gmail.com%27",  # noqa: E501
            json={"value": SIGN_INS},
            complete_qs=True,
        )
        results = action.run({"userPrincipalName": "test@gmail.com"})

    assert results == {"signIns": SIGN_INS}


def test_enable_user():
    action = configured_action(EnableUserAction)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "PATCH",
            "https://graph.microsoft.com/beta/users/test.user@test.onmicrosoft.com",
        )
        results = action.run({"userPrincipalName": "test.user@test.onmicrosoft.com"})

        assert mock.last_request.json() == {"accountEnabled": True}

    assert results is None


def test_disable_user():
    action = configured_action(DisableUserAction)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "PATCH",
            "https://graph.microsoft.com/beta/users/test.user@test.onmicrosoft.com",
        )
        results = action.run({"userPrincipalName": "test.user@test.onmicrosoft.com"})

        assert mock.last_request.json() == {"accountEnabled": False}

    assert results is None
