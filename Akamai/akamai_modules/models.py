from pydantic.v1 import BaseModel, Field


class AkamaiModuleConfiguration(BaseModel):
    host: str = Field(..., description="Host of the tenant")
    client_token: str = Field(..., description="Client token")
    client_secret: str = Field(..., description="Client secret", secret=True)
    access_token: str = Field(..., description="Access Token", secret=True)

    @property
    def base_url(self):
        base_url = self.host.rstrip("/")

        if base_url.startswith("http://"):
            base_url = f"https://{base_url[7:]}"

        if not base_url.startswith("https://"):
            base_url = f"https://{base_url}"

        return base_url
