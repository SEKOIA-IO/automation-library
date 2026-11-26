from pydantic import BaseModel, Field, SecretStr


class NewRelicModuleConfiguration(BaseModel):
    base_url: str = Field(description="Base URL")
    api_key: SecretStr = Field(description="API key")
