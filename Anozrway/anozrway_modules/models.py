from typing import Optional

from pydantic.v1 import BaseModel, Field


class AnozrwayModuleConfiguration(BaseModel):
    anozrway_base_url: str = Field(
        default="https://balise.anozrway.com",
        description="Anozrway API base URL",
    )
    anozrway_token_url: str = Field(
        default="https://auth.anozrway.com/oauth2/token",
        description="Anozrway OAuth2 token URL",
    )
    anozrway_client_id: str = Field(..., description="Anozrway OAuth2 Client ID")
    anozrway_client_secret: str = Field(..., description="Anozrway OAuth2 Client Secret")
    anozrway_x_restrict_access_token: Optional[str] = Field(
        None, description="Anozrway additional authorization token (x-restrict-access header)"
    )
    timeout_seconds: int = Field(default=30, description="HTTP timeout in seconds", ge=1, le=120)
