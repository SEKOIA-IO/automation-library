from pydantic import BaseModel, Field


class FlareIOModuleConfiguration(BaseModel):
    api_key: str = Field(
        ..., description="Flare API key used to authenticate against the API", json_schema_extra={"secret": True}
    )
    tenant_id: int | None = None
