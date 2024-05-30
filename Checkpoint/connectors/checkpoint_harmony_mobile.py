"""Contains CheckpointHarmony connector."""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import orjson
from dateutil.parser import isoparse
from loguru import logger
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from client.http_client import CheckpointHttpClient
from connectors import CheckpointModule

from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


ONE_SECOND = timedelta(seconds=1)


class CheckpointHarmonyMobileConfiguration(DefaultConnectorConfiguration):
    """The CheckpointHarmonyMobile configuration."""

    ratelimit_per_minute: int = 60
    chunk_size: int = 1000
    frequency: int = 60


class CheckpointHarmonyMobileConnector(AsyncConnector):
    """The CheckpointHarmonyMobile connector."""

    name = "CheckpointHarmonyMobileConnector"
    module: CheckpointModule
    configuration: CheckpointHarmonyMobileConfiguration

    _checkpoint_client: CheckpointHttpClient | None = None

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init CheckpointHarmony."""

        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

    @property
    def last_event_date(self) -> datetime:
        """
        Get last event date.

        Returns:
            datetime:
        """
        now = datetime.now(timezone.utc)
        one_hour_ago = (now - timedelta(hours=1)).replace(microsecond=0)

        with self.context as cache:
            last_event_date_str = cache.get("last_event_date")

        # If undefined, retrieve events from the last 1 hour
        if last_event_date_str is None:
            return one_hour_ago

        # Parse the most recent date seen
        last_event_date: datetime = isoparse(last_event_date_str).replace(microsecond=0)

        # We don't retrieve messages older than 1 hour
        if last_event_date < one_hour_ago:
            return one_hour_ago

        return last_event_date

    def get_checkpoint_client(self) -> CheckpointHttpClient:
        """Get CheckpointHttpClient."""
        if self._checkpoint_client is None:
            self._checkpoint_client = CheckpointHttpClient(
                client_id=self.module.configuration.client_id,
                secret_key=self.module.configuration.secret_key,
                auth_url=self.module.configuration.authentication_url,
                base_url=self.module.configuration.base_url,
            )

        return self._checkpoint_client

    async def get_checkpoint_harmony_events(self) -> tuple[list[str], float]:
        """
        Get CheckpointHarmony events.

        Returns:
            tuple[list[str], float]: result event ids and new latest event date in timestamp
        """
        _last_event_date = self.last_event_date + ONE_SECOND
        list_of_events = self.get_checkpoint_client().get_harmony_mobile_alerts(_last_event_date, 100)
        events = [event async for events in list_of_events for event in events]

        logger.info("Fetched {0} events from source", len(events))

        _new_latest_event_date = _last_event_date
        for event in events:
            event_date = event.event_timestamp or event.backend_last_updated or _last_event_date

            if event_date > _new_latest_event_date:
                _new_latest_event_date = event_date

        result: list[str] = await self.push_data_to_intakes(
            [
                orjson.dumps(
                    {
                        **event.dict(),
                        "event_timestamp": (event.event_timestamp.isoformat() if event.event_timestamp else None),
                        "backend_last_updated": (
                            event.backend_last_updated.isoformat() if event.backend_last_updated else None
                        ),
                    }
                ).decode("utf-8")
                for event in events
            ]
        )

        with self.context as cache:
            cache["last_event_date"] = _new_latest_event_date.isoformat()

        return result, _new_latest_event_date.timestamp()

    def run(self) -> None:  # pragma: no cover
        """Runs Crowdstrike Telemetry."""

        while self.running:
            try:
                loop = asyncio.get_event_loop()

                while self.running:
                    processing_start = time.time()

                    message_ids, latest_event_date = loop.run_until_complete(self.get_checkpoint_harmony_events())
                    processing_end = time.time()

                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(message_ids))

                    lag = 0.
                    log_message = "No records to forward"
                    if len(message_ids) > 0:
                        lag = processing_end - latest_event_date
                        log_message = "Pushed {0} records".format(len(message_ids))

                    self.log(message=log_message, level="info")
                    logger.info(
                        "Processing took {processing_time} seconds and {additional_log}",
                        processing_time=(processing_end - processing_start),
                        additional_log=log_message,
                    )
                    EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(lag)

                    FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                        processing_end - processing_start
                    )

                    # compute the remaining sleeping time. If greater than 0, sleep
                    delta_sleep = self.configuration.frequency - lag
                    if delta_sleep > 0:
                        logger.info(
                            f"Next batch of events in the future. Waiting {delta_sleep} seconds",
                        )
                        time.sleep(delta_sleep)

                # Close the current event loop
                if loop.is_running():
                    loop.stop()
                    loop.close()

            except Exception as e:
                logger.error("Error while running Checkpoint Harmony: {error}", error=e)
