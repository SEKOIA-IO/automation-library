from typing import Any

from kiota_abstractions.base_request_configuration import RequestConfiguration
from kiota_abstractions.default_query_parameters import QueryParameters
from kiota_abstractions.native_response_handler import NativeResponseHandler
from kiota_http.middleware.options import ResponseHandlerOption
from msgraph.generated.audit_logs.sign_ins.sign_ins_request_builder import SignInsRequestBuilder
from msgraph.generated.models.sign_in_collection_response import SignInCollectionResponse
from msgraph.generated.users.item.revoke_sign_in_sessions.revoke_sign_in_sessions_post_response import (
    RevokeSignInSessionsPostResponse,
)
from pydantic.v1 import BaseModel

from graph_api.client import GraphApi

from .base import IdArguments, MicrosoftGraphAction, SingleUserArguments


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
    appliedConditionalAccessPolicies: list[Any]
    authenticationContextClassReferences: list[Any]
    authenticationDetails: list[Any]
    authenticationMethodsUsed: list[str]
    authenticationProcessingDetails: list[Any]
    authenticationProtocol: str | None
    authenticationRequirement: str | None
    authenticationRequirementPolicies: list[Any]
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
    networkLocationDetails: list[Any]
    originalRequestId: str | None
    privateLinkDetails: dict[str, Any]
    processingTimeInMilliseconds: int
    resourceDisplayName: str | None
    resourceId: str | None
    resourceServicePrincipalId: str | None
    resourceTenantId: str | None
    riskDetail: str | None
    riskEventTypes_v2: list[Any]
    riskLevelAggregated: str | None
    riskLevelDuringSignIn: str | None
    riskState: str | None
    servicePrincipalCredentialKeyId: str | None
    servicePrincipalCredentialThumbprint: str | None
    servicePrincipalId: str | None
    servicePrincipalName: str | None
    sessionLifetimePolicies: list[Any]
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

    async def query_get_user_signin(
        self, req_conf: RequestConfiguration[SignInsRequestBuilder.SignInsRequestBuilderGetQueryParameters]
    ) -> SignInCollectionResponse | None:  # pragma: no cover
        return await self.client.audit_logs.sign_ins.get(request_configuration=req_conf)

    async def run(self, arguments: IdArguments) -> dict[str, Any]:
        query_params = SignInsRequestBuilder.SignInsRequestBuilderGetQueryParameters(
            filter=f"userId eq '{arguments.id}'"
        )

        request_configuration = RequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())], query_parameters=query_params
        )

        response = await self.query_get_user_signin(request_configuration)

        if response is None:
            raise ValueError("No response received from the server for Get SignIns action.")

        return GraphApi.encode_values_as_dict("signIns", response.value or [])


class RevokeSignInsSessionsAction(MicrosoftGraphAction):
    name = "Revoke SignIns Sessions"
    description = "Invalidates all the refresh tokens issued to applications for a user. Requires the User.ReadWrite.All or Directory.ReadWrite.All permissions."  # noqa: E501

    async def query_revoke_signin(
        self, user_id: str, req_conf: RequestConfiguration[QueryParameters]
    ) -> RevokeSignInSessionsPostResponse | None:  # pragma: no cover
        return await self.client.users.by_user_id(user_id).revoke_sign_in_sessions.post(request_configuration=req_conf)

    async def run(self, arguments: SingleUserArguments) -> None:
        request_configuration: RequestConfiguration[QueryParameters] = RequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())],
        )

        response = await self.query_revoke_signin(arguments.get_user_id(), request_configuration)
        if response is None:
            raise ValueError("No response received from the server for Revoke SignIns Sessions action.")
