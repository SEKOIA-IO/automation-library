"""Contains connector, configuration and module."""

import asyncio
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Optional
from zipfile import BadZipFile

import aiofiles
import orjson
from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from dateutil.parser import isoparse
from loguru import logger
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from client.broadcom_cloud_swg_client import BroadcomCloudSwgClient
from connectors import BroadcomCloudModule
from connectors.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS
from utils import files as file_utils


class BroadcomCloudSwgConnectorConfig(DefaultConnectorConfiguration):
    """Configuration for BroadcomCloudSwgConnector."""

    chunk_size: int = 10000
    frequency: int = 60


class BroadcomCloudSwgConnector(AsyncConnector):
    """BroadcomCloudSwgConnector."""

    name = "BroadcomCloudSwgConnector"

    module: BroadcomCloudModule
    configuration: BroadcomCloudSwgConnectorConfig

    _broadcom_cloud_swg_client: BroadcomCloudSwgClient | None = None
    _rate_limiter: AsyncLimiter | None = None

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init BroadcomCloudSwgConnector."""

        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

    @property
    def last_event_date(self) -> datetime:
        """
        Get last event date.

        Returns:
            datetime:
        """
        now = datetime.utcnow()
        one_hour_ago = (now - timedelta(hours=1)).replace(microsecond=0)

        with self.context as cache:
            last_event_date_str = cache.get("last_event_date")

            # If undefined, retrieve events from the last 1 hour
            if last_event_date_str is None:
                return one_hour_ago

            # Parse the most recent date seen
            last_event_date = isoparse(last_event_date_str)

            # We don't retrieve messages older than 1 hour
            if last_event_date < one_hour_ago:
                return one_hour_ago

            return last_event_date

    @classmethod
    def rate_limiter(cls) -> AsyncLimiter | None:  # pragma: no cover
        """
        Get or initialize rate limiter.

        Returns:
            AsyncLimiter:
        """
        if cls._rate_limiter is None:
            requests_limit = os.getenv("REQUESTS_PER_SECOND_TO_INTAKE")
            if requests_limit is not None and int(requests_limit) > 0:
                cls._rate_limiter = AsyncLimiter(int(requests_limit), 1)

        return cls._rate_limiter

    @classmethod
    @asynccontextmanager
    async def session(cls) -> AsyncGenerator[ClientSession, None]:  # pragma: no cover
        """
        Get or initialize client session if it is not initialized yet.

        Returns:
            ClientSession:
        """
        if cls._session is None:
            cls._session = ClientSession()

        rate_limiter = cls.rate_limiter()

        if rate_limiter:
            async with cls.get_rate_limiter():
                yield cls._session
        else:
            yield cls._session

    @property
    def broadcom_cloud_swg_client(self) -> BroadcomCloudSwgClient:
        """
        Get Broadcom Cloud SWG client.

        Returns:
            BroadcomCloudSwgClient:
        """
        if self._broadcom_cloud_swg_client is not None:
            return self._broadcom_cloud_swg_client

        self._broadcom_cloud_swg_client = BroadcomCloudSwgClient(
            username=self.module.configuration.username,
            password=self.module.configuration.password,
            rate_limiter=self.rate_limiter(),
        )

        return self._broadcom_cloud_swg_client

    async def get_events(self) -> tuple[list[str], datetime]:
        """
        Collects events from platform and push to intakes.

        Returns:
            list[str]:
        """
        end_date = datetime.utcnow()
        start_date = self.last_event_date

        token = None
        continue_processing = True

        data_to_push: list[dict[str, str]] = []
        result: list[str] = []
        latest_date: datetime | None = None

        while continue_processing:
            continue_processing, token, file_name = await self.broadcom_cloud_swg_client.get_report_sync(
                start_date=start_date,
                end_date=end_date,
                token=token,
            )

            try:
                temp_directory, unzipped_files = await file_utils.unzip(file_name)
            except BadZipFile:  # pragma: no cover
                logger.info("Empty zip file. No data to process")

                return [], start_date

            try:
                for file_name in unzipped_files:
                    async with aiofiles.open(file_name) as file:
                        headers = None
                        async for line in file:
                            if line.startswith("#") and headers is None:
                                headers = BroadcomCloudSwgClient.parse_string_as_headers(line)

                                if headers:  # pragma: no cover
                                    logger.info("Headers for current log: {0}".format(" ".join(headers)))
                            else:
                                line_as_dict = BroadcomCloudSwgClient.parse_input_string(line, headers)

                                line_date_time = BroadcomCloudSwgClient.get_date_time_from_data(line_as_dict)
                                if latest_date is None:  # pragma: no cover
                                    latest_date = line_date_time

                                if line_date_time and latest_date and latest_date < line_date_time:
                                    latest_date = line_date_time

                                data_to_push.append(line_as_dict)
                                # data_to_push = BroadcomCloudSwgClient.reduce_list(data_to_push)
                                if len(data_to_push) >= self.configuration.chunk_size:  # pragma: no cover
                                    logger.info("Pushing {0} records to intake".format(len(data_to_push)))
                                    result.extend(
                                        await self.push_data_to_intakes(
                                            [orjson.dumps(event).decode("utf-8") for event in data_to_push]
                                        )
                                    )

                                    data_to_push = []

                    logger.info("Pushing {0} records to intake".format(len(data_to_push)))
                    result.extend(
                        await self.push_data_to_intakes(
                            [orjson.dumps(event).decode("utf-8") for event in data_to_push]
                        )
                    )
                    data_to_push = []
            except Exception as e:  # pragma: no cover
                logger.error("Exception during processing: {}".format(str(e)))

                await file_utils.cleanup_resources([temp_directory], [file_name, *unzipped_files])

                raise e

            await file_utils.cleanup_resources([temp_directory], [file_name, *unzipped_files])

        result_latest_date = latest_date or end_date
        with self.context as cache:  # pragma: no cover
            logger.info(
                "New last event date now is {last_event_date}",
                last_event_date=result_latest_date.isoformat(),
            )

            cache["last_event_date"] = result_latest_date.isoformat()

        return result, result_latest_date

    def run(self) -> None:  # pragma: no cover
        """Runs BroadcomCloudSwgConnector."""
        while self.running:
            try:
                loop = asyncio.get_event_loop()

                while self.running:
                    processing_start = time.time()

                    message_ids, last_event_date = loop.run_until_complete(self.get_events())
                    processing_end = time.time()

                    EVENTS_LAG.labels(intake_key=self.configuration.intake_key).observe(
                        processing_end - last_event_date.timestamp()
                    )

                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(message_ids))

                    log_message = "No records to forward"
                    if len(message_ids) > 0:
                        log_message = "Pushed {0} records".format(len(message_ids))

                    logger.info(log_message)
                    self.log(message=log_message, level="info")

                    FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                        last_event_date.timestamp() - processing_start
                    )

                    if len(message_ids) > 0:
                        self.log(message="Pushed {0} records".format(len(message_ids)), level="info")
                    else:
                        self.log(message="No records to forward", level="info")
                        time.sleep(self.configuration.frequency)

            except Exception as error:
                logger.error("Error while running BroadcomCloudSwgConnector: {error}", error=error)
                self.log_exception(error, message="Failed to forward events")
