from pydantic import BaseModel, Field


class LocateRiskModuleConfiguration(BaseModel):
    api_key: str = Field(..., description="API Key")
    scan_id: str = Field(..., description="Scan ID")
    report_url: str = Field(
        "https://app.locaterisk.com/api/rest/report/export",
        description="Base URL of the LocateRisk report export endpoint",
    )
