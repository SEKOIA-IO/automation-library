"""Contains CheckpointHarmony connector."""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Any, Optional

import orjson
from dateutil.parser import isoparse
from loguru import logger
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import CheckpointModule
from .client.http_client import CheckpointHttpClient
from .metrics import FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS
from .timestepper import TimeStepper


class CheckpointHarmonyMobileConfiguration(DefaultConnectorConfiguration):
    """The CheckpointHarmonyMobile configuration."""

    ratelimit_per_minute: int = 60
    chunk_size: int = 100
    frequency: int = 60
    hours_ago: int = 6
    timedelta: int = 15


class CheckpointHarmonyMobileConnector(AsyncConnector):
    """The CheckpointHarmonyMobile connector."""

    name = "CheckpointHarmonyMobileConnector"
    module: CheckpointModule
    configuration: CheckpointHarmonyMobileConfiguration

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init CheckpointHarmony."""

        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self.data_path)

    @property
    def stepper(self) -> TimeStepper:
        with self.context as cache:
            most_recent_date_requested_str = cache.get("last_event_date")

        if most_recent_date_requested_str is None:
            return TimeStepper.create(
                self,
                self.configuration.frequency,
                self.configuration.timedelta,
                self.configuration.hours_ago,
            )

        # parse the most recent requested date
        most_recent_date_requested = isoparse(most_recent_date_requested_str)

        now = datetime.now(timezone.utc)
        one_month_ago = now - timedelta(days=30)
        if most_recent_date_requested < one_month_ago:
            most_recent_date_requested = one_month_ago

        return TimeStepper.create_from_time(
            self,
            most_recent_date_requested,
            self.configuration.frequency,
            self.configuration.timedelta,
        )

    def update_stepper(self, recent_date: str) -> None:
        with self.context as cache:
            app_key_name_in_cache = "last_event_date"
            cache[app_key_name_in_cache] = recent_date

    @cached_property
    def checkpoint_client(self) -> CheckpointHttpClient:
        """Get CheckpointHttpClient."""
        return CheckpointHttpClient(
            client_id=self.module.configuration.client_id,
            secret_key=self.module.configuration.secret_key,
            auth_url=self.module.configuration.authentication_url,
            base_url=self.module.configuration.base_url,
            max_rate=self.configuration.ratelimit_per_minute,
            time_period=60.0,
        )

    async def fetch_checkpoint_harmony_events(self, start: datetime, end: datetime, limit: int) -> list[str]:
        list_of_events = self.checkpoint_client.get_harmony_mobile_alerts(start_from=start, end_at=end, limit=limit)
        events = [event async for events in list_of_events for event in events]
        batch_events = [orjson.dumps(event).decode("utf-8") for event in events]

        if len(batch_events) > 0:
            self.log("Forwarded %d events" % len(batch_events), level="info")

        else:
            self.log("No events forwarded", level="info")

        result: list[str] = await self.push_data_to_intakes(batch_events)
        return result

    def run(self) -> None:  # pragma: no cover
        while self.running:
            try:
                while self.running:
                    loop = asyncio.get_event_loop()

                    for start, end in self.stepper.ranges():
                        # check if the trigger should stop
                        if not self.running:
                            break

                        duration_start = time.time()

                        results = loop.run_until_complete(
                            self.fetch_checkpoint_harmony_events(
                                start=start, end=end, limit=self.configuration.chunk_size
                            )
                        )
                        OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(results))

                        # Save the most recent date seen
                        self.update_stepper(end.isoformat())

                        # compute the duration of the last events fetching
                        duration = int(time.time() - duration_start)
                        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(duration)

                    # Close the current event loop
                    if loop.is_running():
                        loop.stop()
                        loop.close()

            except Exception as e:
                logger.error(f"Error while running Checkpoint Harmony: {e}", error=e)
                self.log_exception(e)
