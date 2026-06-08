from pydantic import BaseModel


class FlareIOModuleConfiguration(BaseModel):
    api_key: str
    tenant_id: int | None = None
