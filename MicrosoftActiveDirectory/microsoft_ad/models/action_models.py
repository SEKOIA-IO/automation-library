from pydantic.v1 import BaseModel, Field


class UserAccountArguments(BaseModel):
    basedn: str | None = Field(None, description="")
    username: str | None = Field(
        None,
        description="",
    )
    display_name: str | None = Field(None, description="Filter by displayName to narrow results")
    apply_to_all: bool = Field(False, description="Apply action to all matching users instead of failing on multiple")


class ResetPassUserArguments(UserAccountArguments):
    new_password: str | None = Field(
        None,
        description="",
    )
