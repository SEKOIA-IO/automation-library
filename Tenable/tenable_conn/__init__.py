from pydantic import BaseModel, Field
from sekoia_automation.module import Module


class TenableModuleConfiguration(BaseModel):
    base_url: str = Field(..., description="Base URL")
    access_token: str = Field(..., description="Access Token")
    secret_key: str = Field(..., description="Secret Key", secret=True)


class TenableModule(Module):
    configuration: TenableModuleConfiguration