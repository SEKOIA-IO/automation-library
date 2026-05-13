from pydantic.v1 import BaseModel, Field


class NetskopeModuleConfiguration(BaseModel):
    base_url: str | None = Field(None, description="API base URL")
