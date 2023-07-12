from pydantic import BaseModel, Field


class CybereasonModuleConfiguration(BaseModel):
    base_url: str = Field(..., description="API base URL")
    username: str = Field(..., description="The username to use to authenticate against the API")
    password: str = Field(secret=True, description="The password to use to authenticate against the API")
