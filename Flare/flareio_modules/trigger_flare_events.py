import time
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Any

import orjson
import requests
from flareio import FlareApiClient
from flareio.ratelimit import Limiter
from requests.adapters import HTTPAdapter
from sekoia_automation.checkpoint import CheckpointCursor
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from urllib3.util import Retry

from flareio_modules import FlareIOModule
from flareio_modules.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


class FlareEventsConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    page_size: int = 100
    initial_hours_lookback: int = 1
    throttle_seconds: float = 0.25


class FlareEventsConnector(Connector):
    module: FlareIOModule
    configuration: FlareEventsConnectorConfiguration

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.cursor = CheckpointCursor(path=self.data_path)

    @cached_property
    def requests_session(self) -> requests.Session:
        session = requests.Session()
        retries = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[429, 502, 503, 504],
            allowed_methods={"GET", "POST"},
            backoff_max=15,
        )
        session.mount("https://", HTTPAdapter(max_retries=retries))
        return session

    @cached_property
    def client(self) -> FlareApiClient:
        return FlareApiClient(
            api_key=self.module.configuration.api_key,
            tenant_id=self.module.configuration.tenant_id,
            session=self.requests_session,
        )

    @cached_property
    def limiter(self) -> Limiter:
        return Limiter.from_seconds(self.configuration.throttle_seconds)

    def _build_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "size": self.configuration.page_size,
            "order": "asc",
        }

        if self.cursor.offset:
            payload["from"] = self.cursor.offset
            return payload

        start_timestamp = datetime.now(tz=timezone.utc) - timedelta(hours=self.configuration.initial_hours_lookback)
        payload["from"] = None
        payload["filters"] = {
            "estimated_created_at": {
                "gte": start_timestamp.isoformat(),
            }
        }
        return payload

    @staticmethod
    def _extract_event(event: Any) -> dict[str, Any] | None:
        if not isinstance(event, dict):
            return None

        # The SDK may return hydrated events wrapped under "activity".
        activity = event.get("activity")
        if isinstance(activity, dict):
            return dict(activity)

        return dict(event)

    def _iter_flare_events(self) -> Iterator[tuple[dict[str, Any] | None, Any]]:
        payload = self._build_payload()

        # Reuse the connector's own configured limiter as the SDK's per-event limiter so
        # `throttle_seconds` is the single source of truth for pacing (avoids double throttling).
        for result in self.client.scroll_events(
            method="POST",
            pages_url="/firework/v4/events/tenant/_search",
            events_url="/firework/v2/activities/",
            json=payload,
            _events_limiter=self.limiter,
        ):
            next_cursor = getattr(result, "next", None)
            event = getattr(result, "event", None)

            # Defensive: tolerate a plain dict shape as well as the SDK's ScrollEventsResult.
            if isinstance(result, dict):
                next_cursor = result.get("next", next_cursor)
                event = result.get("event", event)

            extracted_event = self._extract_event(event)
            yield extracted_event, next_cursor

    def next_batch(self) -> None:
        batch_start_time = time.time()

        latest_next_cursor = self.cursor.offset
        batch_of_events: list[str] = []

        for event, next_cursor in self._iter_flare_events():
            if event is not None:
                batch_of_events.append(orjson.dumps(event).decode("utf-8"))

            if next_cursor:
                latest_next_cursor = next_cursor

        intake_key = self.configuration.intake_key

        if batch_of_events:
            self.push_events_to_intakes(events=batch_of_events)
            self.log(f"Forwarded {len(batch_of_events)} events to the intake", level="info")
            OUTCOMING_EVENTS.labels(intake_key=intake_key).inc(len(batch_of_events))
            EVENTS_LAG.labels(intake_key=intake_key).set(time.time() - batch_start_time)
        else:
            self.log("No events to forward", level="info")

        if latest_next_cursor and latest_next_cursor != self.cursor.offset:
            self.cursor.offset = latest_next_cursor

        batch_duration = time.time() - batch_start_time
        FORWARD_EVENTS_DURATION.labels(intake_key=intake_key).observe(batch_duration)

        delta_sleep = self.configuration.frequency - int(batch_duration)
        if delta_sleep > 0:
            time.sleep(delta_sleep)

    def run(self) -> None:  # pragma: no cover
        self.log(message="Start fetching Flare events", level="info")

        while self.running:
            try:
                self.next_batch()
            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
