from pydantic import BaseModel, Field
from sekoia_automation.module import Module


class VaronisModuleConfiguration(BaseModel):
    base_url: str = Field(..., description="Base domain")
    api_key: str = Field(..., description="API key", json_schema_extra={"secret": True})


class VaronisModule(Module):
    configuration: VaronisModuleConfiguration
