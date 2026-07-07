from pydantic import BaseModel, Field


class FlareIOModuleConfiguration(BaseModel):
    api_key: str = Field(secret=True, description="Flare API key used to authenticate against the API")  # type: ignore[call-overload]
    tenant_id: int | None = None
