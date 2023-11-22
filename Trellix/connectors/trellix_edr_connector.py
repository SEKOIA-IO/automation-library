"""Contains connector, configuration and module."""
import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import orjson
from aiolimiter import AsyncLimiter
from dateutil.parser import isoparse
from loguru import logger
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from client.http_client import TrellixHttpClient
from connectors import TrellixModule

from connectors.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


class TrellixEdrConnectorConfig(DefaultConnectorConfiguration):
    """Configuration for TrellixEdrConnector."""


class TrellixEdrConnector(AsyncConnector):
    """TrellixEdrConnector class to work with EDR events."""

    name = "TrellixEdrConnector"

    module: TrellixModule
    configuration: TrellixEdrConnectorConfig

    _trellix_client: TrellixHttpClient | None = None

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init TrellixEdrConnector."""

        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

    def last_event_date(self, name: str) -> datetime:
        """
        Get last event date for .

        Returns:
            datetime:
        """
        now = datetime.now(timezone.utc)
        one_week_ago = (now - timedelta(days=7)).replace(microsecond=0)

        with self.context as cache:
            last_event_date_str = cache.get(name)

            # If undefined, retrieve events from the last 7 days
            if last_event_date_str is None:
                return one_week_ago

            # Parse the most recent date seen
            last_event_date = isoparse(last_event_date_str)

            # We don't retrieve messages older than one week
            if last_event_date < one_week_ago:
                return one_week_ago

            return last_event_date

    @property
    def trellix_client(self) -> TrellixHttpClient:
        """
        Get trellix client.

        Returns:
            TrellixHttpClient:
        """
        if self._trellix_client is not None:
            return self._trellix_client

        rate_limiter = AsyncLimiter(self.module.configuration.ratelimit_per_minute)

        self._trellix_client = TrellixHttpClient(
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
            api_key=self.module.configuration.api_key,
            auth_url=self.module.configuration.auth_url,
            base_url=self.module.configuration.base_url,
            rate_limiter=rate_limiter,
        )

        return self._trellix_client

    async def get_trellix_edr_events(self) -> list[str]:
        """
        Process trellix edr events.

        Returns:
            List[str]:
        """
        # Check alerts. If there is any - push to intake
        alerts = await self.trellix_client.get_edr_alerts(
            self.last_event_date('alerts'), self.module.configuration.records_per_request,
        )
        result = await self.push_data_to_intakes(
            [orjson.dumps(event.dict()).decode("utf-8") for event in alerts]
        )

        # Check threats. If there is any - push to intake
        threats = await self.trellix_client.get_edr_threats(
            self.last_event_date("threats"), self.module.configuration.records_per_request,
        )
        result.extend(
            await self.push_data_to_intakes(
                [orjson.dumps(event.dict()).decode("utf-8") for event in threats]
            )
        )

        # Go through each threat and get detections and affected hosts information based on same last_event_date
        for threat in threats:
            threat_id: str = threat.id

            offset = 0
            while True:
                detections = await self.trellix_client.get_edr_threat_detections(
                    threat_id,
                    self.last_event_date("threats"),
                    self.module.configuration.records_per_request,
                    offset,
                )
                result.extend(
                    await self.push_data_to_intakes(
                        [orjson.dumps(event.dict()).decode("utf-8") for event in detections]
                    )
                )
                offset = offset + self.module.configuration.records_per_request

                if len(detections) == 0:
                    break


        result: list[str] = await self.push_data_to_intakes(
            [orjson.dumps(event.attributes.dict()).decode("utf-8") for event in events]
        )

        return result

    async def get_threat_detections(self, threat_id: str, start_date: datetime, end_date: datetime) -> list[str]:
        """
        Get threat detections.

        Args:
            threat_id: str
            start_date: datetime
            end_date: datetime

        Returns:
            list[str]
        """
        result = []

        offset = 0
        while True:
            detections = await self.trellix_client.get_edr_threat_detections(
                threat_id,
                start_date,
                end_date,
                self.module.configuration.records_per_request,
                offset,
            )

            result_data = [
                orjson.dumps(
                    {
                        **event.dict(),
                        "threatId": threat_id
                    }
                ).decode("utf-8")
                for event in detections
            ]

            result.extend(await self.push_data_to_intakes(result_data))
            offset = offset + self.module.configuration.records_per_request

            if len(detections) == 0:
                break

        return result

    async def get_threat_affectedhosts(self, threat_id: str, start_date: datetime, end_date: datetime) -> list[str]:
        """
        Get threat affectedhosts.

        Args:
            threat_id: str
            start_date: datetime
            end_date: datetime

        Returns:
            list[str]
        """
        result = []

        offset = 0
        while True:
            affectedhosts = await self.trellix_client.get_edr_threat_affectedhosts(
                threat_id,
                start_date,
                end_date,
                self.module.configuration.records_per_request,
                offset,
            )

            result_data = [
                orjson.dumps(
                    {
                        **event.dict(),
                        "threatId": threat_id
                    }
                ).decode("utf-8")
                for event in affectedhosts
            ]

            result.extend(await self.push_data_to_intakes(result_data))
            offset = offset + self.module.configuration.records_per_request

            if len(affectedhosts) == 0:
                break

        return result

    def run(self) -> None:  # pragma: no cover
        """Runs TrellixEdr."""
        previous_processing_end = None

        while self.running:
            try:
                loop = asyncio.get_event_loop()

                while self.running:
                    processing_start = time.time()
                    if previous_processing_end is not None:
                        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).observe(
                            processing_start - previous_processing_end
                        )

                    message_ids: list[str] = loop.run_until_complete(self.get_trellix_edr_events())
                    processing_end = time.time()
                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(message_ids))

                    log_message = "No records to forward"
                    if len(message_ids) > 0:
                        log_message = "Pushed {0} records".format(len(message_ids))

                    logger.info(log_message)
                    self.log(message=log_message, level="info")
                    logger.info(log_message)
                    logger.info(
                        "Processing took {processing_time} seconds",
                        processing_time=(processing_end - processing_start),
                    )

                    FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                        processing_end - processing_start
                    )

                    previous_processing_end = processing_end

            except Exception as e:
                logger.error("Error while running Trellix EPO: {error}", error=e)
