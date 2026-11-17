from datetime import datetime, timedelta
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from rapid7_insightvm.asset_connector.helpers import format_datetime, parse_datetime


class Window(BaseModel):
    """
    Represents a collection window with the current and comparison times, along with pagination information.

    ``full_resync`` (set after a checkpoint reset) also re-emits the findings still open and unchanged.
    ``short_attempts`` counts the traversals of this window whose pages ended before ``totalPages``.
    A window stored before these fields existed is read with their defaults.
    """

    CLOUD_SYNC_DELAY: ClassVar[timedelta] = timedelta(hours=1)
    MIN_WINDOW_DURATION: ClassVar[timedelta] = timedelta(hours=2)

    current_time: str
    comparison_time: str | None = None
    page: int = Field(default=0, ge=0)
    cursor: str | None = None
    full_resync: bool = False
    short_attempts: int = Field(default=0, ge=0)

    model_config = ConfigDict(frozen=True)

    @property
    def first_run(self) -> bool:
        return self.comparison_time is None

    @classmethod
    def next_from(cls, comparison_time: str | None, now: datetime, full_resync: bool = False) -> Window | None:
        start = parse_datetime(comparison_time)
        end = now.replace(microsecond=0) - cls.CLOUD_SYNC_DELAY
        if start is not None and end - start < cls.MIN_WINDOW_DURATION:
            return None
        return cls(
            comparison_time=format_datetime(start) if start is not None else None,
            current_time=format_datetime(end),
            # A first run already emits every open finding
            full_resync=full_resync and start is not None,
        )

    def at_page(self, page: int, cursor: str | None) -> Window:
        return Window(**{**self.model_dump(), "page": page, "cursor": cursor})

    def retry(self) -> Window:
        """The same window, requested again from its first page after a short traversal."""
        return Window(**{**self.model_dump(), "page": 0, "cursor": None, "short_attempts": self.short_attempts + 1})
