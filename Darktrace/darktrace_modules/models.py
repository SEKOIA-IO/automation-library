from pydantic import BaseModel, Field


class DarktraceModuleConfiguration(BaseModel):
    api_url: str | None = Field(default=None, description="The url of the Darktrace appliance")
    public_key: str | None = Field(default=None, description="The public key to the Darktrace API")
    private_key: str | None = Field(
        default=None,
        description="The private key to the Darktrace API",
        json_schema_extra={"secret": True},
    )
