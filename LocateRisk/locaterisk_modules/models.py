from pydantic import BaseModel, Field, field_validator


class LocateRiskModuleConfiguration(BaseModel):
    api_key: str = Field(..., description="API Key", json_schema_extra={"secret": True})
    base_url: str = Field(
        "https://app.locaterisk.com/",
        description="Base URL of the LocateRisk platform",
    )

    @field_validator("base_url")
    @classmethod
    def _require_https(cls, value: str) -> str:
        # Reject non-HTTPS base URLs at configuration time so the API key
        # (sent as a Bearer token) is never transmitted in cleartext.
        if not value.lower().startswith("https://"):
            raise ValueError("base_url must use HTTPS")
        return value
