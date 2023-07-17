from pydantic import BaseModel, Field


class OktaModuleConfiguration(BaseModel):
    base_url: str = Field(..., description="The url to your Okta tenant")
    apikey: str = Field(secret=True, description="The APIkey to authenticate calls to the API")
