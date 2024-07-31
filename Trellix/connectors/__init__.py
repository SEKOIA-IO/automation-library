"""Module ad connector for Trellix."""

from pydantic import BaseModel, HttpUrl
from sekoia_automation.module import Module


class TrellixModuleConfig(BaseModel):
    """Configuration for TrellixModule."""

    client_id: str
    client_secret: str
    api_key: str
    delay: int = 60
    auth_url: HttpUrl = HttpUrl("https://iam.mcafee-cloud.com/iam/v1.1", scheme="https")
    base_url: HttpUrl = HttpUrl("https://api.manage.trellix.com", scheme="https")


class TrellixModule(Module):
    """TrellixModule."""

    configuration: TrellixModuleConfig
