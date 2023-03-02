from pydantic import BaseModel

from .base import MicrosoftGraphAction, SingleUserArguments


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
    description = "Get the last sign ins of an Azure AD user. Requires the AuditLog.Read.All and Directory.Read.All permissions."  # noqa: E501
    results_model = GetSignInsResults

    def run(self, arguments: SingleUserArguments):
        params = {}

        if arguments.id:
            params["$filter"] = f"userId eq '{arguments.id}'"
        elif arguments.userPrincipalName:
            params["$filter"] = f"userPrincipalName eq '{arguments.userPrincipalName}'"

        response = self.client.get(
            "/auditLogs/signIns",
            params=params,
        )
        response.raise_for_status()

        return {"signIns": response.json()["value"]}
