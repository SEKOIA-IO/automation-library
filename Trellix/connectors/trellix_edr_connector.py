"""Contains connector, configuration and module."""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple

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

    frequency: int = 300
    ratelimit_per_minute: int = 60
    ratelimit_per_day: int = 2000
    records_per_request: int = 100


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

        rate_limiter = AsyncLimiter(self.configuration.ratelimit_per_minute)
        daily_rate_limiter = AsyncLimiter(self.configuration.ratelimit_per_day)

        self._trellix_client = TrellixHttpClient(
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
            api_key=self.module.configuration.api_key,
            auth_url=self.module.configuration.auth_url,
            base_url=self.module.configuration.base_url,
            rate_limiter=rate_limiter,
            rate_limiter_per_day=daily_rate_limiter,
        )

        return self._trellix_client

    async def populate_alerts(self) -> Tuple[list[str], datetime]:
        """
        Process trellix edr alerts.

        Returns:
            List[str]:
        """
        start_date = self.last_event_date("alerts")
        alerts = await self.trellix_client.get_edr_alerts(
            start_date,
            self.configuration.records_per_request,
        )
        logger.info("Got {total} alerts from {start_date}", start_date=start_date, total=len(alerts))

        result: list[str] = await self.push_data_to_intakes(
            [orjson.dumps(event.dict()).decode("utf-8") for event in alerts]
        )

        last_event_date = start_date
        for alert in alerts:
            alert_detection_date = isoparse(alert.attributes.detectionDate)
            if alert_detection_date.replace(tzinfo=timezone.utc) > last_event_date.replace(tzinfo=timezone.utc):
                last_event_date = alert_detection_date

        with self.context as cache:
            cache["alerts"] = last_event_date.isoformat()

        return result, last_event_date

    async def populate_threats(self, end_date: datetime | None = None) -> Tuple[list[str], datetime]:
        """
        Populate threats.

        Returns:
            list[str]
        """
        result: list[str] = []

        start_date = self.last_event_date("threats")

        if end_date is None:
            end_date = datetime.now(timezone.utc).replace(microsecond=0)

        most_recent_threat_date = start_date

        offset = 0
        while True:
            threats = await self.trellix_client.get_edr_threats(
                start_date,
                end_date,
                self.configuration.records_per_request,
                offset,
            )
            logger.info(
                "Got {total} threats from {start_date} to {end_date} and offset {offset}",
                start_date=start_date,
                end_date=end_date,
                offset=offset,
                total=len(threats),
            )

            result_data = [orjson.dumps(event.dict(exclude_none=True)).decode("utf-8") for event in threats]
            result.extend(await self.push_data_to_intakes(result_data))

            for threat in threats:
                threat_date = isoparse(threat.attributes.lastDetected).replace(tzinfo=timezone.utc)

                if threat_date > most_recent_threat_date:
                    most_recent_threat_date = threat_date

                if threat.id is None:
                    raise Exception("Threat id is None")

                result.extend(await self.get_threat_detections(threat.id, start_date, end_date))
                result.extend(await self.get_threat_affectedhosts(threat.id, start_date, end_date))

            offset = offset + self.configuration.records_per_request

            if len(threats) == 0:
                break

        with self.context as cache:
            cache["threats"] = end_date.isoformat()

        return result, most_recent_threat_date

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
                self.configuration.records_per_request,
                offset,
            )
            logger.info(
                "Got {total} dectections for threat {threat_id} from {start_date} to {end_date} and offset {offset}",
                threat_id=threat_id,
                start_date=start_date,
                end_date=end_date,
                offset=offset,
                total=len(detections),
            )

            result_data = [
                orjson.dumps({**event.dict(exclude_none=True), "threatId": threat_id}).decode("utf-8")
                for event in detections
            ]

            result.extend(await self.push_data_to_intakes(result_data))
            offset = offset + self.configuration.records_per_request

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
                self.configuration.records_per_request,
                offset,
            )
            logger.info(
                "Got {total} affectedhosts for threat {threat_id} from {start_date} to {end_date} and offset {offset}",
                threat_id=threat_id,
                start_date=start_date,
                end_date=end_date,
                offset=offset,
                total=len(affectedhosts),
            )

            result_data = [
                orjson.dumps({**event.dict(exclude_none=True), "threatId": threat_id}).decode("utf-8")
                for event in affectedhosts
            ]

            result.extend(await self.push_data_to_intakes(result_data))
            offset = offset + self.configuration.records_per_request

            if len(affectedhosts) == 0:
                break

        return result

    async def async_run(self) -> None:  # pragma: no cover
        while self.running:
            try:
                processing_start = time.time()

                message_threats_ids, most_recent_threat_date = await self.populate_threats()
                message_alerts_ids, most_recent_alert_date = await self.populate_alerts()

                processing_end = time.time()

                message_ids = message_alerts_ids + message_threats_ids

                EVENTS_LAG.labels(intake_key=self.configuration.intake_key, type="threats").set(
                    processing_end - most_recent_threat_date.timestamp()
                )

                EVENTS_LAG.labels(intake_key=self.configuration.intake_key, type="alerts").set(
                    processing_end - most_recent_alert_date.timestamp()
                )

                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(message_ids))

                log_message = "No records to forward"
                if len(message_ids) > 0:
                    log_message = "Pushed {0} records".format(len(message_ids))

                self.log(message=log_message, level="info")

                processing_time = processing_end - processing_start
                logger.info(
                    "Processing took {processing_time} seconds",
                    processing_time=processing_time,
                )

                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(processing_time)

                # compute the remaining sleeping time. If greater than 0 and no messages where fetched, pause the connector
                delta_sleep = self.configuration.frequency - processing_time
                if len(message_ids) == 0 and delta_sleep > 0:
                    self.log(message=f"Next batch in the future. Waiting {delta_sleep} seconds", level="info")

                    await asyncio.sleep(delta_sleep)
            except Exception as e:
                self.log_exception(e, message="Error while running Trellix EDR")
                await asyncio.sleep(self.configuration.frequency)

    def run(self) -> None:  # pragma: no cover
        """Runs TrellixEdr."""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_run())
