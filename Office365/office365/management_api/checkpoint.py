from datetime import datetime, timedelta, timezone
from pathlib import Path

from dateutil.parser import isoparse


class Checkpoint:
    def __init__(self, path: Path, intake_key: str):
        self._context: Path = path / f"o365_{intake_key}_last_pull"
        self._most_recent_date_seen: datetime | None = None

    @property
    def offset(self) -> datetime:
        now = datetime.now(timezone.utc)

        if self._most_recent_date_seen is None:

            try:
                # read the most recent date seen from the context
                most_recent_date_seen_str = self._context.read_text()
                most_recent_date_seen = isoparse(most_recent_date_seen_str)
            except Exception:
                # if not defined, set the most recent date seen to now
                most_recent_date_seen = now

            self._most_recent_date_seen = most_recent_date_seen

        # check if the date is older than the 7 days ago
        one_week_ago = now - timedelta(days=7)
        if self._most_recent_date_seen < one_week_ago:
            self._most_recent_date_seen = one_week_ago

        return self._most_recent_date_seen

    @offset.setter
    def offset(self, last_message_date: datetime | None):
        if last_message_date is not None:
            if self.offset is None or last_message_date > self.offset:
                self._most_recent_date_seen = last_message_date
                self._context.write_text(last_message_date.isoformat())
