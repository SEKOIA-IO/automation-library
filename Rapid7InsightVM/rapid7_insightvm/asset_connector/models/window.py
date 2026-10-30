from typing import ClassVar
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from rapid7_insightvm.asset_connector.helpers import format_datetime, parse_datetime


class Window(BaseModel):
    """
    Represents a collection window with the current and comparison times, along with pagination information.
    """

    CLOUD_SYNC_DELAY: ClassVar[timedelta] = timedelta(hours=1)
    MIN_WINDOW_DURATION: ClassVar[timedelta] = timedelta(hours=2)

    current_time: str
    comparison_time: str | None = None
    page: int = Field(default=0, ge=0)
    cursor: str | None = None

    model_config = ConfigDict(frozen=True)

    @property
    def first_run(self) -> bool:
        return self.comparison_time is None

    @classmethod
    def next_from(cls, comparison_time: str | None, now: datetime) -> "Window | None":
        start = parse_datetime(comparison_time)
        end = now.replace(microsecond=0) - cls.CLOUD_SYNC_DELAY
        if start is not None and end - start < cls.MIN_WINDOW_DURATION:
            return None
        return cls(
            comparison_time=format_datetime(start) if start is not None else None,
            current_time=format_datetime(end),
        )

    def at_page(self, page: int, cursor: str | None) -> "Window":
        return Window(**{**self.model_dump(), "page": page, "cursor": cursor})
