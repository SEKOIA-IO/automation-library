from pydantic import BaseModel, Field


class PolyswarmModuleConfiguration(BaseModel):
    apikey: str = Field(..., description="PolySwarm API key", json_schema_extra={"secret": True})
    community: str = Field(default="default", description="PolySwarm community")
