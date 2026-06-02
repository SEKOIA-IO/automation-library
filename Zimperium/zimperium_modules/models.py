from pydantic.v1 import BaseModel, Field


class ZimperiumModuleConfiguration(BaseModel):
    base_url: str
    client_id: str
    client_secret: str
