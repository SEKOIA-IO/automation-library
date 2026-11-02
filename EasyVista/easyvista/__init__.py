from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator
from sekoia_automation.module import Module


class EasyVistaConfiguration(BaseModel):
    base_url: str = Field(description="HTTPS protocol and host of the EasyVista server, without a path")
    tenant_id: str = Field(
        min_length=1, pattern=r"\S", description="Non-empty EasyVista account number, including any leading zeros"
    )
    use_token: bool = True
    username: str | None = None
    password: str | None = Field(default=None, json_schema_extra={"secret": True})
    token: str | None = Field(default=None, json_schema_extra={"secret": True})
    verify_ssl: bool = True

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
            or parts.path not in {"", "/"}
            or parts.query
            or parts.fragment
        ):
            raise ValueError("base_url must contain only a protocol and host")
        return value.rstrip("/")


class EasyVistaModule(Module):
    configuration: EasyVistaConfiguration  # type: ignore[override]
