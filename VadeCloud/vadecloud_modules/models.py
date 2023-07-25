from pydantic import BaseModel, Field


class VadeCloudModuleConfiguration(BaseModel):
    hostname: str = Field("https://cloud.vadesecure.com", description="API hostname")
    login: str = Field(..., description="API login")
    password: str = Field(..., description="API password", secret=True)
