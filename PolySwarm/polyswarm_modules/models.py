from pydantic import BaseModel, Field


class PolyswarmModuleConfiguration(BaseModel):
    # The platform builds the configuration form label from the property name, so the
    # name is the label a customer reads. Sekoia confirmed the title key is ignored.
    API_Key: str = Field(..., description="PolySwarm API key", json_schema_extra={"secret": True})
    community: str = Field(default="default", description="PolySwarm community")
