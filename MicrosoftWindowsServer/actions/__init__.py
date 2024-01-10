"""MicrosoftModule."""
from pydantic import BaseModel, Field
from sekoia_automation.module import Module


class MicrosoftModuleConfiguration(BaseModel):
    """Configuration for MicrosoftModule."""

    username: str = Field(required=True, description="Microsoft Remote Server username")
    password: str = Field(secret=True, required=True, description="Microsoft Remote Server password")


class MicrosoftModule(Module):
    """MicrosoftModule."""

    configuration: MicrosoftModuleConfiguration
