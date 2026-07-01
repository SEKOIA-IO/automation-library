from pydantic.v1 import Field
from sekoia_automation.connector import DefaultConnectorConfiguration

from mokn.domain import MoknThreatLevel


class MoknLoginAttemptsTriggerConfiguration(DefaultConnectorConfiguration):
    frequency: int = Field(60, ge=1, description="Polling interval in seconds")
    chunk_size: int = Field(
        100,
        ge=1,
        le=1000,
        description="Maximum number of events forwarded to the intake in a single batch",
    )
    page_size: int = Field(
        100,
        ge=1,
        le=1000,
        description="Number of login summaries requested per page",
    )
    initial_lookback_minutes: int = Field(
        5,
        ge=1,
        description="How far to look back when no checkpoint exists yet",
    )
    threat_levels: list[MoknThreatLevel] = Field(
        default_factory=lambda: [MoknThreatLevel.HIGH],
        description="Threat levels filter applied to MokN login attempts",
    )
    pending: bool = Field(
        True,
        description="Whether to restrict the query to pending attempts",
    )
    statuses: list[int] = Field(
        default_factory=lambda: [
            # MokN Internal Mapping
            1,
            0,
            4,
            2,
            8,
            6,
            -1,
            5,
            10,
            9,
        ],
        description=("List of MokN status codes included in the polling query. " "Accepts integer values."),
    )
