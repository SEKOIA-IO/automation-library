from pydantic import BaseModel, Field


class CyberArkModuleConfiguration(BaseModel):
    auth_base_url: str = Field(..., description="The CyberArk Identity endpoint")
    login_name: str = Field(..., description="Login name")
    password: str = Field(..., description="Password", secret=True)
    application_id: str = Field(..., description="Application identifier")

