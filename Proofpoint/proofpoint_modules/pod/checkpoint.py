from datetime import datetime, timedelta, timezone
from pathlib import Path

from dateutil.parser import isoparse
from sekoia_automation.storage import PersistentJSON


class Checkpoint:
    def __init__(self, path: Path):
        self._context: PersistentJSON = PersistentJSON("context.json", path)
        self._most_recent_date_seen: datetime | None = None

    @property
    def offset(self) -> datetime | None:
        if self._most_recent_date_seen is None:
            with self._context as cache:
                most_recent_date_seen_str = cache.get("most_recent_date_seen")
                # if undefined, retrieve events from the last minute
                if most_recent_date_seen_str is None:
                    return None

                most_recent_date_seen = isoparse(most_recent_date_seen_str)

                # check if the date is older than the 30 days ago
                thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
                if most_recent_date_seen < thirty_days_ago:
                    most_recent_date_seen = thirty_days_ago

                self._most_recent_date_seen = most_recent_date_seen

        return self._most_recent_date_seen

    @offset.setter
    def offset(self, last_message_date: datetime | None):
        if last_message_date is not None:
            if self.offset is None or last_message_date > self.offset:
                with self._context as cache:
                    self._most_recent_date_seen = last_message_date
                    cache["most_recent_date_seen"] = self._most_recent_date_seen.isoformat()
