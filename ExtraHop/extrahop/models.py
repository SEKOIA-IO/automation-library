from pydantic import BaseModel, Field


class ExtraHopModuleConfiguration(BaseModel):
    base_url: str = Field(..., description="API base URL")
    client_id: str = Field(..., description="Client ID")
    client_secret: str = Field(secret=True, description="Client Secret")

    @property
    def tenant_url(self):
        base_url = self.base_url.rstrip("/")

        if base_url.startswith("http://"):
            base_url = f"https://{base_url[7:]}"

        if not base_url.startswith("https://"):
            base_url = f"https://{base_url}"

        return base_url
