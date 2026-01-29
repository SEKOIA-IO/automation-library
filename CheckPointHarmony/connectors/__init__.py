"""Package for the Checkpoint module and connectors."""

from pydantic import BaseModel, Field
from sekoia_automation.module import Module


class CheckpointModuleConfiguration(BaseModel):
    """The configuration of the Checkpoint module."""

    client_id: str = Field(..., description="Client Id to interact with Checkpoint API")
    secret_key: str = Field(secret=True, description="Secret key to work with Checkpoint API")
    authentication_url: str = Field(..., description="Authentication url to authenticate Checkpoint API")
    base_url: str = Field(
        default="https://cloudinfra-gw.portal.checkpoint.com",
        description="Base url to interact with Checkpoint API",
    )


class CheckpointModule(Module):
    """The Checkpoint module."""

    configuration: CheckpointModuleConfiguration
