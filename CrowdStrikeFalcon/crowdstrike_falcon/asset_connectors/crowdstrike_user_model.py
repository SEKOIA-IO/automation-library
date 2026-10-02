from pydantic import BaseModel, Field


class CrowdStrikeUserAccount(BaseModel):
    """Represents an account descriptor attached to a CrowdStrike user entity."""

    model_config = {"extra": "ignore"}

    dataSource: str | None = None
    domain: str | None = None
    samAccountName: str | None = None
    objectSid: str | None = None
    objectGuid: str | None = None
    enabled: bool | None = None


class CrowdStrikeUserRole(BaseModel):
    """Represents a role assigned to a CrowdStrike user entity."""

    model_config = {"extra": "ignore"}

    type: str | None = None


class CrowdStrikeUser(BaseModel):
    """
    Represents a user entity as returned by the CrowdStrike Identity Protection GraphQL API.

    All fields are optional to accommodate partial API responses.
    Field names match the GraphQL response field names exactly (camelCase).
    """

    model_config = {"extra": "ignore"}

    # Identity
    entityId: str | None = None
    type: str | None = None

    # Display names
    primaryDisplayName: str | None = None
    secondaryDisplayName: str | None = None

    # Timestamps
    creationTime: str | None = None

    # Risk
    riskScore: float | None = None
    riskScoreSeverity: str | None = None

    # Accounts (e.g. Active Directory, Azure AD)
    accounts: list[CrowdStrikeUserAccount] = Field(default_factory=list)

    # Contact
    emailAddresses: list[str] = Field(default_factory=list)

    # Roles
    roles: list[CrowdStrikeUserRole] = Field(default_factory=list)
