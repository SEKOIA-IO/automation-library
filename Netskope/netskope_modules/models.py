from pydantic import BaseModel, Field


class NetskopeModuleConfiguration(BaseModel):
    base_url: str = Field(description="API base URL")
