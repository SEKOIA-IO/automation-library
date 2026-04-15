import datetime

from pydantic.v1 import BaseModel, Field
from sekoia_automation.asset_connector.models.connector import DefaultAssetConnectorConfiguration
from sekoia_automation.module import Module


class MicrosoftADConfiguration(BaseModel):
    servername: str = Field(..., description="Remote machine IP or Name")
    admin_username: str = Field(..., description="Admin username")
    admin_password: str = Field(..., secret=True, description="Admin password")  # type: ignore


class MicrosoftADModule(Module):
    configuration: MicrosoftADConfiguration


class MicrosoftADConnectorConfiguration(DefaultAssetConnectorConfiguration):
    basedn: str | None = Field(None, description="Active directory basedn")


class LDAPUserAttributes(BaseModel):
    """Parses raw LDAP user attribute dictionaries returned by the ldap3 client."""

    objectClass: list[str] | None = None
    cn: str | None = None
    sn: str | None = None
    givenName: str | None = None
    distinguishedName: str | None = None
    instanceType: int | None = None
    whenCreated: datetime.datetime | None = None
    whenChanged: datetime.datetime | None = None
    displayName: str | None = None
    uSNCreated: int | None = None
    uSNChanged: int | None = None
    name: str | None = None
    objectGUID: str | None = None
    userAccountControl: int | None = None
    badPwdCount: int | None = None
    codePage: int | None = None
    countryCode: int | None = None
    badPasswordTime: datetime.datetime | None = None
    lastLogoff: datetime.datetime | None = None
    lastLogon: datetime.datetime | None = None
    pwdLastSet: datetime.datetime | None = None
    primaryGroupID: int | None = None
    objectSid: str | None = None
    accountExpires: datetime.datetime | None = None
    logonCount: int | None = None
    sAMAccountName: str | None = None
    sAMAccountType: int | None = None
    userPrincipalName: str | None = None
    objectCategory: str | None = None
    dSCorePropagationData: list[datetime.datetime] | None = None
    mail: str | None = None
    member_of: list[str] | None = Field(None, alias="memberOf")

    class Config:
        # Accept datetime objects with any tzinfo (e.g. ldap3's OffsetTzInfo)
        arbitrary_types_allowed = True
        allow_population_by_field_name = True
