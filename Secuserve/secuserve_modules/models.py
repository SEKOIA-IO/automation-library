from pydantic import BaseModel, Field


class SecuserveModuleConfiguration(BaseModel):
    api_host: str = Field(
        "https://www.security-mail.net",
        description="URL of the e-securemail administration console",
    )
