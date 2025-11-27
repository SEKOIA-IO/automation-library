from pydantic import BaseModel, Field
from sekoia_automation.module import Module

class WorkdayConfiguration(BaseModel):
    """Module-level configuration for Workday integration"""

    workday_host: str = Field(..., description="Workday host URL (e.g., wd3-services1.myworkday.com)")
    tenant_name: str = Field(..., description="Workday tenant name")
    client_id: str = Field(..., description="OAuth 2.0 Client ID")
    client_secret: str = Field(..., description="OAuth 2.0 Client Secret", secret=True)
    refresh_token: str = Field(..., description="Non-expiring refresh token", secret=True)

class WorkdayModule(Module):
    """Workday module"""
    configuration: WorkdayConfiguration