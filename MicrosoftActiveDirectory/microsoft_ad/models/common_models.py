from pydantic.v1 import BaseModel, Field

from sekoia_automation.module import Module


class MicrosoftADConfiguration(BaseModel):
    servername: str = Field(..., description="Remote machine IP or Name")
    admin_username: str = Field(..., description="Admin username")
    admin_password: str = Field(..., secret=True, description="Admin password")  # type: ignore


class MicrosoftADModule(Module):
    configuration: MicrosoftADConfiguration