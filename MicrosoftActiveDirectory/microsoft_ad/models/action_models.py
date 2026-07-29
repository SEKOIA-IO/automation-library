from pydantic import BaseModel, Field


class UserAccountArguments(BaseModel):
    basedn: str | None = Field(None, description="")
    username: str | None = Field(
        None,
        description="",
    )
    domain_controller: str | None = Field(
        None,
        description="Override LDAP server to target specific domain controller when operating across child domains",
    )
    email: str | None = Field(None, description="Filter by email address (mail attribute) to narrow results")
    apply_to_all: bool = Field(False, description="Apply action to all matching users instead of failing on multiple")


class ResetPassUserArguments(UserAccountArguments):
    new_password: str | None = Field(
        None,
        description="",
    )
