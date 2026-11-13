from pydantic import BaseModel, Field


class WorkdayClientConfiguration(BaseModel):
    """Configuration model for Workday client"""

    workday_host: str = Field(
        ..., description="Workday API hostname, without scheme or path (e.g., wd3-services1.myworkday.com)"
    )
    tenant_name: str = Field(
        ..., description="Workday tenant identifier, first path segment of the Workday URL (e.g., acme)"
    )
    client_id: str = Field(..., description="OAuth 2.0 Client ID of the Workday API Client")
    # FIXED: Use json_schema_extra instead of deprecated 'secret' parameter
    client_secret: str = Field(..., description="OAuth 2.0 Client Secret", json_schema_extra={"secret": True})
    refresh_token: str = Field(..., description="Non-expiring refresh token", json_schema_extra={"secret": True})
