from pydantic import BaseModel, Field, field_validator


class LocateRiskModuleConfiguration(BaseModel):
    api_key: str = Field(..., description="API Key", json_schema_extra={"secret": True})
    scan_id: str = Field(..., description="Scan ID", json_schema_extra={"secret": True})
    report_url: str = Field(
        "https://app.locaterisk.com/api/rest/report/export",
        description="Base URL of the LocateRisk report export endpoint",
    )

    @field_validator("report_url")
    @classmethod
    def _require_https(cls, value: str) -> str:
        # Reject non-HTTPS report URLs at configuration time so the API key
        # (sent as a Bearer token) is never transmitted in cleartext.
        if not value.lower().startswith("https://"):
            raise ValueError("report_url must use HTTPS")
        return value
