from pydantic.v1 import BaseModel, Field
from sekoia_automation.module import Module


class NozomiConfiguration(BaseModel):
    key_name: str = Field(..., description="Nozomi Key Name")
    key_token: str = Field(..., secret=True, description="Nozomi Key Token")
    base_url: str = Field(
        "https://vantagetechalliancesinstance.customers.us1.vantage.nozominetworks.io",
        description="Base URL for Nozomi Vantage API",
    )


class NozomiModule(Module):
    configuration: NozomiConfiguration
