from pydantic import BaseModel, Field, HttpUrl


class SalesforceModuleConfig(BaseModel):
    """Configuration for SalesforceModule."""

    client_secret: str = Field(secret=True)
    client_id: str
    base_url: HttpUrl
