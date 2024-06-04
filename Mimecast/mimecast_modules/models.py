from pydantic import BaseModel, Field


class MimecastModuleConfiguration(BaseModel):
    client_id: str = Field(..., description="Client ID")
    client_secret: str = Field(secret=True, description="Client Secret")
