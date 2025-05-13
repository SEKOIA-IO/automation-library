from pydantic import BaseModel, Field


class LookoutModuleConfiguration(BaseModel):
    host: str = Field(..., description="Base URL")
    api_token: str = Field(..., description="API Token", secret=True)

    @property
    def base_url(self):
        base_url = self.host.rstrip("/")

        if base_url.startswith("http://"):
            base_url = f"https://{base_url[7:]}"

        if not base_url.startswith("https://"):
            base_url = f"https://{base_url}"

        return base_url
