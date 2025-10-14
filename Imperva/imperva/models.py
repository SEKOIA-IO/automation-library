from pydantic.v1 import BaseModel, Field


class ImpervaModuleConfiguration(BaseModel):
    base_url: str = Field(..., description="Imperva API base URL")
    api_id: str = Field(..., description="Imperva API ID")
    api_key: str = Field(..., description="Imperva API key")
    keys: dict = Field({}, description="Encryption keys")
