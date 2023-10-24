from pydantic import BaseModel, Field


class DarktraceModuleConfiguration(BaseModel):
    api_url: str = Field(..., description="The url of the Darktrace appliance")
    public_key: str = Field(..., description="The public key to the Darktrace API")
    private_key: str = Field(secret=True, description="The private key to the Darktrace API")
