from pydantic import BaseModel, Field


class LocateRiskModuleConfiguration(BaseModel):
    api_key: str = Field(..., description="API Key", json_schema_extra={"secret": True})
    scan_id: str = Field(..., description="Scan ID", json_schema_extra={"secret": True})
    report_url: str = Field(
        "https://app.locaterisk.com/api/rest/report/export",
        description="Base URL of the LocateRisk report export endpoint",
    )
