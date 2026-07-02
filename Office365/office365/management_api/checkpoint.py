from datetime import UTC, datetime, timedelta
from pathlib import Path

from dateutil.parser import isoparse
from sekoia_automation.utils import capture_retry_error
from tenacity import retry, stop_after_attempt, wait_exponential


class Checkpoint:
    def __init__(self, path: Path, intake_key: str):
        self._context: Path = path / f"o365_{intake_key}_last_pull"
        self._most_recent_date_seen: datetime | None = None

    @property
    def offset(self) -> datetime:
        now = datetime.now(UTC)

        if self._most_recent_date_seen is None:
            most_recent_date_seen_str: str | None = self.read(filepath=self._context)
            if most_recent_date_seen_str:
                most_recent_date_seen = isoparse(most_recent_date_seen_str)

            else:
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
                self.write(filepath=self._context, data=last_message_date.isoformat())

    @retry(
        reraise=True,
        wait=wait_exponential(max=6),
        stop=stop_after_attempt(10),
        retry_error_callback=capture_retry_error,
    )
    def read(self, filepath: Path) -> str | None:
        if not filepath.is_file():
            return None

        with filepath.open("rt") as file:
            result = file.read()

        return result

    @retry(
        reraise=True,
        wait=wait_exponential(max=6),
        stop=stop_after_attempt(10),
        retry_error_callback=capture_retry_error,
    )
    def write(self, filepath: Path, data: bytes | str) -> None:
        if isinstance(data, str):
            data = data.encode("utf-8")

        with filepath.open("wb") as out:
            out.write(data)
