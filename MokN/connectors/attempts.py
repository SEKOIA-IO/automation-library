import json
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Any, Iterator

from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import Connector
from sekoia_automation.storage import PersistentJSON

from client import ApiClient
from connectors.configuration import MoknLoginAttemptsTriggerConfiguration
from module import MoknModule
from mokn.domain import AttemptCursor, AttemptQuery
from mokn.repositories import AttemptRepository
from mokn.services import AttemptService


class MoknLoginAttemptsTrigger(Connector):
    """Sekoia connector that polls MokN attempts and pushes normalized events."""

    description = "Collect MokN bait attempts and forward them to Sekoia.io"
    module: MoknModule
    configuration: MoknLoginAttemptsTriggerConfiguration

    @property
    def frequency(self) -> int:
        return self.configuration.frequency

    @property
    def checkpoint(self) -> CheckpointDatetime:
        start_at = timedelta(minutes=self.configuration.initial_lookback_minutes)
        return CheckpointDatetime(self.data_path, start_at=start_at)

    @cached_property
    def context(self) -> PersistentJSON:
        return PersistentJSON("context.json", self.data_path)

    @staticmethod
    def _to_second(value: datetime) -> datetime:
        return value.astimezone(UTC).replace(microsecond=0)

    def _get_cursor(self) -> AttemptCursor:
        cursor = self._to_second(self.checkpoint.offset)
        with self.context as cache:
            cached_date = cache.get("most_recent_date_seen")
            seen_ids = set()
            if cached_date is not None:
                cached_datetime = self._to_second(self.repository.parse_datetime(cached_date))
                if cached_datetime == cursor:
                    seen_ids = set(cache.get("seen_ids_at_most_recent_date", []))
        return AttemptCursor(second=cursor, seen_ids=seen_ids)

    def _set_cursor(self, cursor: AttemptCursor) -> None:
        normalized_value = self._to_second(cursor.second)
        self.checkpoint.offset = normalized_value
        with self.context as cache:
            cached_seen_ids = set(cache.get("seen_ids_at_most_recent_date", []))
            cached_date = cache.get("most_recent_date_seen")

            if cached_date is not None:
                cached_datetime = self._to_second(self.repository.parse_datetime(cached_date))
                if cached_datetime == normalized_value:
                    cursor.seen_ids |= cached_seen_ids

            cache["most_recent_date_seen"] = normalized_value.isoformat()
            cache["seen_ids_at_most_recent_date"] = sorted(cursor.seen_ids)

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            base_url=self.module.configuration.base_url,
            api_token=self.module.configuration.api_token,
        )

    @property
    def query(self) -> AttemptQuery:
        return AttemptQuery(
            page_size=self.configuration.page_size,
            statuses=list(self.configuration.statuses),
            threat_levels=list(self.configuration.threat_levels),
            pending=self.configuration.pending,
        )

    @cached_property
    def repository(self) -> AttemptRepository:
        return AttemptRepository(
            client=self.client,
            verify_ssl=self.module.configuration.verify_ssl,
        )

    @cached_property
    def service(self) -> AttemptService:
        return AttemptService(repository=self.repository)

    def iterate(self, cursor: AttemptCursor) -> Iterator[tuple[list[dict[str, Any]], datetime | None]]:
        batch_size = self.configuration.page_size
        current_cursor = AttemptCursor(
            second=self._to_second(cursor.second),
            seen_ids=set(cursor.seen_ids),
        )

        while batch_size == self.configuration.page_size:
            summaries = self.service.list_attempt_summaries(
                current_cursor.second,
                self.query,
            )
            batch_size = len(summaries)
            events: list[dict[str, Any]] = []
            latest_event_date: datetime | None = None
            batch_latest_second: datetime | None = None
            batch_ids_at_latest_second: set[int] = set()
            new_ids_in_current_second: set[int] = set()

            for summary in summaries:
                summary_second = self._to_second(summary.updated_time)
                summary_id = summary.attempt_id

                if summary_second == current_cursor.second and summary_id in current_cursor.seen_ids:
                    continue

                detail = self.service.get_attempt_detail(summary_id)
                normalized_attempt = self.service.normalize_attempt(summary, detail)
                events.append(
                    {
                        "event_type": "mokn_bait_attempt",
                        **normalized_attempt.to_dict(),
                    }
                )

                updated_time = summary.updated_time
                if latest_event_date is None or updated_time > latest_event_date:
                    latest_event_date = updated_time

                if summary_second == current_cursor.second:
                    new_ids_in_current_second.add(summary_id)

                if batch_latest_second is None or summary_second > batch_latest_second:
                    batch_latest_second = summary_second
                    batch_ids_at_latest_second = {summary_id}
                elif summary_second == batch_latest_second:
                    batch_ids_at_latest_second.add(summary_id)

            next_cursor = AttemptCursor(
                second=current_cursor.second,
                seen_ids=set(current_cursor.seen_ids),
            )

            if batch_latest_second is None:
                yield events, latest_event_date
                break

            if batch_latest_second == current_cursor.second:
                if not new_ids_in_current_second:
                    yield events, latest_event_date
                    break
                current_cursor.seen_ids |= new_ids_in_current_second
                next_cursor = AttemptCursor(
                    second=current_cursor.second,
                    seen_ids=set(current_cursor.seen_ids),
                )
            else:
                current_cursor = AttemptCursor(
                    second=batch_latest_second,
                    seen_ids=set(batch_ids_at_latest_second),
                )
                next_cursor = AttemptCursor(
                    second=current_cursor.second,
                    seen_ids=set(current_cursor.seen_ids),
                )

            self._next_cursor = next_cursor
            yield events, latest_event_date

            if batch_size < self.configuration.page_size:
                break

    def next_run(self) -> None:
        processing_start = datetime.now(UTC)
        total_number_of_events = 0
        cursor = self._get_cursor()
        self._next_cursor = cursor

        for events, _ in self.iterate(cursor):
            if events:
                serialized_events = [json.dumps(event) for event in events]
                self.push_events_to_intakes(events=serialized_events)
                total_number_of_events += len(events)
                next_cursor = self._next_cursor
                if next_cursor.second != cursor.second or next_cursor.seen_ids != cursor.seen_ids:
                    self._set_cursor(next_cursor)
                    cursor = next_cursor

        processing_time = (datetime.now(UTC) - processing_start).total_seconds()

        delta_sleep = self.frequency - processing_time
        sleep_time = max(delta_sleep, 0)
        self.log(
            message=(
                f"MokN run completed with {total_number_of_events} fetched event(s). "
                f"Next wait time: {sleep_time:.2f}s"
            ),
            level="info",
        )
        if total_number_of_events == 0 and delta_sleep > 0:
            self._stop_event.wait(delta_sleep)
