from pydantic import BaseModel, HttpUrl
from sekoia_automation.module import Module


class WizModuleConfig(BaseModel):
    """Configuration for WizModule."""

    tenant_url: HttpUrl
    client_id: str
    client_secret: str


class WizModule(Module):
    """WizModule."""

    configuration: WizModuleConfig
