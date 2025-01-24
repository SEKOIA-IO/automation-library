from pydantic import BaseModel, HttpUrl
from sekoia_automation.module import Module


class WizModuleConfig(BaseModel):
    """Configuration for WizModule."""

    tenant_url: HttpUrl = HttpUrl("https://iam.mcafee-cloud.com/iam/v1.1", scheme="https")
    client_id: str
    client_secret: str


class WizModule(Module):
    """WizModule."""

    configuration: WizModuleConfig
