"""Package with connectors to work with Broadcom Cloud SWG."""

from pydantic import BaseModel, Field
from sekoia_automation.module import Module


class BroadcomCloudModuleConfig(BaseModel):
    """Configuration for BroadcomCloudModuleConfig."""

    ratelimit_per_minute: int = 60
    username: str = Field(required=True, description="Broadcom Cloud Username")
    password: str = Field(required=True, description="Broadcom Cloud Password")


class BroadcomCloudModule(Module):
    """BroadcomCloudModule."""

    configuration: BroadcomCloudModuleConfig
