from pydantic.v1 import BaseModel, Field
from sekoia_automation.module import Module


class WatchGuardConfiguration(BaseModel):
    username: str = Field(..., description="WatchGuard username")
    password: str = Field(..., secret=True, description="WatchGuard password")
    account_id: str = Field(..., description="WatchGuard account ID")
    application_key: str = Field(..., secret=True, description="WatchGuard application key")
    base_url: str = Field(
        "https://api.deu.cloud.watchguard.com",
        description="Base URL for WatchGuard API",
    )


class WatchGuardModule(Module):
    configuration: WatchGuardConfiguration
