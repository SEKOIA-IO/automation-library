from pydantic import BaseModel


class ZimperiumModuleConfiguration(BaseModel):
    base_url: str
    client_id: str
    client_secret: str
