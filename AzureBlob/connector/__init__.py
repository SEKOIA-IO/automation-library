"""This module contains connector, metrics."""
from pydantic import BaseModel, Field
from sekoia_automation.module import Module


class AzureBlobStorageModuleConfig(BaseModel):
    """Module Configuration."""

    container_name: str
    account_name: str
    account_key: str = Field(secret=True)


class AzureBlobStorageModule(Module):
    """AzureBlobStorageModule."""

    configuration: AzureBlobStorageModuleConfig
