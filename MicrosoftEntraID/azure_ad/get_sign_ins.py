from pydantic import BaseModel
import asyncio

from .base import MicrosoftGraphAction, SingleUserArguments, IdArguments

from kiota_abstractions.native_response_handler import NativeResponseHandler
from kiota_http.middleware.options import ResponseHandlerOption
from msgraph.generated.users.item.messages.messages_request_builder import MessagesRequestBuilder


class DeviceDetail(BaseModel):
    browser: str | None
    deviceId: str | None
    displayName: str | None
    isCompliant: bool
    isManaged: bool
    operatingSystem: str | None
    trustType: str | None


class GeoCoordinates(BaseModel):
    altitude: float | None
    latitude: float
    longitude: float


class SignInLocation(BaseModel):
    city: str | None
    countryOrRegion: str | None
    geoCoordinates: GeoCoordinates | None
    state: str | None


class SignInStatus(BaseModel):
    additionalDetails: str | None
    errorCode: int
    failureReason: str | None


class SignIn(BaseModel):
    appDisplayName: str | None
    appId: str | None
    appliedConditionalAccessPolicies: list
    authenticationContextClassReferences: list
    authenticationDetails: list
    authenticationMethodsUsed: list[str]
    authenticationProcessingDetails: list
    authenticationProtocol: str | None
    authenticationRequirement: str | None
    authenticationRequirementPolicies: list
    autonomousSystemNumber: int
    clientAppUsed: str | None
    clientCredentialType: str | None
    conditionalAccessStatus: str | None
    correlationId: str | None
    createdDateTime: str | None
    crossTenantAccessType: str | None
    deviceDetail: DeviceDetail
    federatedCredentialId: str | None
    flaggedForReview: bool
    homeTenantId: str | None
    homeTenantName: str | None
    id: str | None
    incomingTokenType: str | None
    ipAddress: str | None
    ipAddressFromResourceProvider: str | None
    isInteractive: bool
    isTenantRestricted: bool
    location: SignInLocation
    networkLocationDetails: list
    originalRequestId: str | None
    privateLinkDetails: dict
    processingTimeInMilliseconds: int
    resourceDisplayName: str | None
    resourceId: str | None
    resourceServicePrincipalId: str | None
    resourceTenantId: str | None
    riskDetail: str | None
    riskEventTypes_v2: list
    riskLevelAggregated: str | None
    riskLevelDuringSignIn: str | None
    riskState: str | None
    servicePrincipalCredentialKeyId: str | None
    servicePrincipalCredentialThumbprint: str | None
    servicePrincipalId: str | None
    servicePrincipalName: str | None
    sessionLifetimePolicies: list
    signInEventTypes: list[str]
    signInIdentifier: str | None
    signInIdentifierType: str | None
    status: SignInStatus
    tokenIssuerName: str | None
    tokenIssuerType: str | None
    uniqueTokenIdentifier: str | None
    userAgent: str | None
    userDisplayName: str | None
    userId: str | None
    userPrincipalName: str | None
    userType: str | None


class GetSignInsResults(BaseModel):
    signIns: list[SignIn]


class GetSignInsAction(MicrosoftGraphAction):
    name = "Get SignIns"
    description = "Get the last sign ins of an Azure AD user. Requires the AuditLog.Read.All and Directory.Read.All app permissions."  # noqa: E501
    # results_model doesn't support async model
    # results_model = GetSignInsResults

    async def query_get_user_signin(self, req_conf):
        return await self.client.audit_logs.sign_ins.get(request_configuration=req_conf)

    async def run(self, arguments: IdArguments):
        query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
            filter=f"userId eq '{arguments.id}'"
        )
        request_configuration = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())], query_parameters=query_params
        )

        response = await self.query_get_user_signin(request_configuration)

        response.raise_for_status()

        return {"signIns": response.json()["value"]}


class RevokeSignInsSessionsAction(MicrosoftGraphAction):
    name = "Revoke SignIns Sessions"
    description = "Invalidates all the refresh tokens issued to applications for a user. Requires the User.ReadWrite.All or Directory.ReadWrite.All permissions."  # noqa: E501

    async def query_revoke_signin(self, signIn_param, req_conf):
        return await self.client.users.by_user_id(signIn_param).revoke_sign_in_sessions.post(
            request_configuration=req_conf
        )

    async def run(self, arguments: SingleUserArguments):
        request_configuration = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())],
        )
        signIn_param = arguments.id or arguments.userPrincipalName

        response = await self.query_revoke_signin(signIn_param, request_configuration)

        response.raise_for_status()
