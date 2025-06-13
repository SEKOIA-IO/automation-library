from pydantic.v1 import BaseModel, Field


class HornetsecurityModuleConfiguration(BaseModel):
    api_token: str = Field(secret=True, description="API token for the Hornetsecurity platform")
    hostname: str = Field(
        "https://cp.hornetsecurity.com/api/v0",
        description="API url of the Hornetsecurity platform",
    )
