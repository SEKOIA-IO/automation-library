from pydantic import BaseModel, Field
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

    # Max backfill on first run and max catch-up after an interruption
    max_historical_days: int = Field(
        default=180,
        ge=1,
        description=(
            "Number of days of history collected on the first run, and maximum lag caught up after an interruption"
        ),
    )
