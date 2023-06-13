from pydantic import BaseModel, Field
from sekoia_automation.module import Module


class OpenAIConfiguration(BaseModel):
    api_key: str = Field(secret=True, description="API Key to use to connect to OpenAI API endpoints")


class OpenAIModule(Module):
    configuration: OpenAIConfiguration
