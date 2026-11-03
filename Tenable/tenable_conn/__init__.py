from pydantic import BaseModel, Field
from sekoia_automation.module import Module


class TenableModuleConfiguration(BaseModel):
    base_url: str = Field(..., description="Base URL")
    access_key: str = Field(..., description="Access key")
    secret_key: str = Field(..., description="Secret Key")


class TenableModule(Module):
    # The annotation is read by the SDK to build the configuration model; SDK >= 1.27 is typed (py.typed)
    configuration: TenableModuleConfiguration  # type: ignore[override]
