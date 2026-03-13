from pydantic.v1 import BaseModel
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.module import Module


class UstaModuleConfig(BaseModel):
    """Configuration for USTA."""

    api_key: str


class UstaModule(Module):
    """USTA Module."""

    configuration: UstaModuleConfig


class UstaATPConnectorConfiguration(DefaultConnectorConfiguration):
    # Run loop frequency (seconds)
    frequency: float = 300.0

    # Max backfill on first run
    max_historical_days: int = 180
