from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator


class EasyVistaConfiguration(BaseModel):
    base_url: str = Field(description="HTTPS protocol and host of the EasyVista server, without a path")
    tenant_id: str = Field(
        min_length=1, pattern="\\S", description="Non-empty EasyVista account number, including any leading zeros"
    )
    use_token: bool = Field(
        default=True, description="Use access token (Bearer) authentication, recommended; false: Basic authentication"
    )
    username: str | None = Field(default=None, description="REST API user login; required when use_token is false")
    password: str | None = Field(
        default=None,
        json_schema_extra={"secret": True},
        description="REST API user password; required when use_token is false",
    )
    token: str | None = Field(
        default=None,
        json_schema_extra={"secret": True},
        description="EasyVista access token; required when use_token is true",
    )
    verify_ssl: bool = Field(default=True, description="Verify the server TLS certificate")

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme != "https":
            raise ValueError("base_url must use HTTPS")
        if (
            not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or (parts.path not in {"", "/"})
            or parts.query
            or parts.fragment
        ):
            raise ValueError("base_url must contain only a protocol and host")
        return value.rstrip("/")
