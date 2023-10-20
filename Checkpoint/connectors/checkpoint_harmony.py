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


class CheckpointHarmonyConfiguration(DefaultConnectorConfiguration):
    """The CheckpointHarmony configuration."""

    ratelimit_per_minute: int = 60
    chunk_size: int = 1000


class CheckpointHarmonyConnector(AsyncConnector):
    """The CheckpointHarmony connector."""

    name = "CheckpointHarmonyConnector"
    module: CheckpointModule
    configuration: CheckpointHarmonyConfiguration

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
        last_event_date = isoparse(last_event_date_str).replace(microsecond=0)

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
        _last_event_date = self.last_event_date
        events = await self.get_checkpoint_client().get_harmony_mobile_alerts(_last_event_date, 100)

        logger.info("Fetched {0} events from source", len(events))

        _new_latest_event_date = _last_event_date
        for event in events:
            # Swagger says that it should have "%m/%d/%Y %H:%M:%S" but all other values that we pass are in ISO format
            # So we try to parse it as ISO and if it fails we parse it as "%m/%d/%Y %H:%M:%S"
            # See 200 response here:
            # https://app.swaggerhub.com/apis-docs/Check-Point/harmony-mobile/1.0.0-oas3#/Events/GetAlerts
            try:
                event_date = isoparse(event.event_timestamp)
            except ValueError:
                event_date = datetime.strptime(event.event_timestamp, "%m/%d/%Y %H:%M:%S")

            if event_date > _new_latest_event_date:
                _new_latest_event_date = event_date

        result: list[str] = await self.push_data_to_intakes(
            [orjson.dumps(event.dict()).decode("utf-8") for event in events]
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

                    EVENTS_LAG.labels(intake_key=self.configuration.intake_key).observe(
                        processing_end - latest_event_date
                    )

                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(message_ids))

                    log_message = "No records to forward"
                    if len(message_ids) > 0:
                        log_message = "Pushed {0} records".format(len(message_ids))

                    self.log(message=log_message, level="info")
                    logger.info(
                        "Processing took {processing_time} seconds and {additional_log}",
                        processing_time=(processing_end - processing_start),
                        additional_log=log_message,
                    )

                    FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                        processing_end - processing_start
                    )

            except Exception as e:
                logger.error("Error while running CrowdStrike Telemetry: {error}", error=e)
