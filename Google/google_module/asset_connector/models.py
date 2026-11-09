"""
Pydantic models of the Admin SDK Directory API responses.

Docs: https://developers.google.com/workspace/admin/directory/reference/rest
"""

from pydantic import BaseModel, ConfigDict


class DirectoryModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class UserName(DirectoryModel):
    givenName: str | None = None
    familyName: str | None = None
    fullName: str | None = None
    displayName: str | None = None


class UserOrganization(DirectoryModel):
    name: str | None = None
    title: str | None = None
    department: str | None = None
    location: str | None = None
    primary: bool | None = None


class UserExternalId(DirectoryModel):
    type: str | None = None
    value: str | None = None


class DirectoryUser(DirectoryModel):
    """User resource of `users.list`."""

    id: str
    primaryEmail: str
    creationTime: str
    name: UserName | None = None
    isAdmin: bool | None = None
    isDelegatedAdmin: bool | None = None
    suspended: bool | None = None
    archived: bool | None = None
    isEnrolledIn2Sv: bool | None = None
    lastLoginTime: str | None = None
    orgUnitPath: str | None = None
    organizations: list[UserOrganization] | None = None
    externalIds: list[UserExternalId] | None = None


class DirectoryGroup(DirectoryModel):
    """Group resource of `groups.list`."""

    id: str
    email: str
    name: str | None = None
    description: str | None = None
    directMembersCount: str | None = None


class DirectoryMember(DirectoryModel):
    """Member resource of `members.list`."""

    id: str | None = None
    type: str | None = None
