from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import ValidationInfo

DEMO_API_KEY = "1" * 64


class NextronValhallaSigmaRulesModuleConfiguration(BaseModel):
    valhalla_api_key: str = Field(default=DEMO_API_KEY, json_schema_extra={"secret": True})
    sekoia_api_key: str = Field(..., json_schema_extra={"secret": True})
    sekoia_base_url: str = Field(default="https://api.sekoia.io")
    community_uuid: str | None = Field(default=None)

    @field_validator("valhalla_api_key", "sekoia_api_key", "sekoia_base_url")
    @classmethod
    def _reject_blank(cls, value: str, info: ValidationInfo) -> str:
        """Strip surrounding whitespace and reject values that are empty or
        whitespace-only.

        Stripping matters because these are copy-pasted: a trailing newline
        on an API key would otherwise be interpolated straight into the
        ``Authorization`` header, and a stray space in the base URL into
        every request path.
        """
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{info.field_name} must not be empty — set it in the module configuration.")
        return stripped

    @field_validator("sekoia_base_url")
    @classmethod
    def _require_https(cls, value: str) -> str:
        """The bearer token goes in every request header; never send it over
        plain HTTP. Checked here (not only in ``SekoiaClient``) so the SDK
        reports a module configuration error before the trigger starts."""
        if not value.lower().startswith("https://"):
            raise ValueError(f"sekoia_base_url must use https:// (got {value!r})")
        return value

    @field_validator("community_uuid")
    @classmethod
    def _blank_community_is_none(cls, value: str | None) -> str | None:
        """Optional: an empty or whitespace-only value means "not set"."""
        if value is None:
            return None
        return value.strip() or None
