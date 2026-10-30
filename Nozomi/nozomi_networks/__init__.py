from pydantic import BaseModel, Field
from sekoia_automation.module import Module


class NozomiConfiguration(BaseModel):
    key_name: str = Field(..., description="Nozomi Key Name")
    key_token: str = Field(..., description="Nozomi Key Token", json_schema_extra={"secret": True})
    base_url: str = Field(..., description="Base URL for Nozomi Vantage API")


class NozomiModule(Module):
    configuration: NozomiConfiguration
