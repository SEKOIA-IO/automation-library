from pydantic.v1 import BaseModel, Field, SecretStr


class OktaModuleConfiguration(BaseModel):
    base_url: str = Field(..., description="The url to your Okta tenant")
    apikey: SecretStr = Field(..., description="The APIkey to authenticate calls to the API")
