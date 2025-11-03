from pydantic.v1 import BaseModel, Field


class UserAccountArguments(BaseModel):
    basedn: str | None = Field(None, description="")
    username: str | None = Field(
        None,
        description="",
    )


class ResetPassUserArguments(UserAccountArguments):
    new_password: str | None = Field(
        None,
        description="",
    )
