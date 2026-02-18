from pydantic.v1 import BaseModel, Field


class SalesforceCustomModuleConfiguration(BaseModel):
    salesforce_domain: str = Field(..., description="Salesforce domain name")
    consumer_key: str = Field(..., description="Consumer key of the External Client App", secret=True)
    consumer_secret: str = Field(..., description="Consumer secret of the External Client App", secret=True)
