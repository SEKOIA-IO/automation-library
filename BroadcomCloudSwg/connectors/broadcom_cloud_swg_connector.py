"""Contains connector, configuration and module."""

import asyncio
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from functools import reduce
from typing import Any, AsyncGenerator, Coroutine, Optional
from urllib.parse import urljoin
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

        with self.context as cache:
            last_event_date_str = cache.get("last_event_date")

            # If undefined, retrieve events from the last 1 hour
            if last_event_date_str is None:
                return (now - timedelta(hours=1)).replace(microsecond=0)

            # Parse the most recent date seen
            last_event_date = isoparse(last_event_date_str)

            one_day_ago = (now - timedelta(days=1)).replace(microsecond=0)
            # We don't retrieve messages older than 1 days
            if last_event_date < one_day_ago:
                return one_day_ago

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

            if requests_limit is None:
                cls._rate_limiter = AsyncLimiter(1, 1)

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
            async with rate_limiter:
                logger.info("Initialized session with rate limiter : {0} r/s".format(rate_limiter.max_rate))
                yield cls._session
        else:
            logger.info("Initialized session with empty rate limiter.")
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

    async def push_broadcom_data_to_intakes(self, events: list[str], index: int) -> int:  # pragma: no cover
        """
        Custom method to push events to intakes.

        Args:
            events: list[str]
            index: int

        Returns:
            list[str]:
        """
        self._last_events_time = datetime.utcnow()
        batch_api = urljoin(self.configuration.intake_server, "batch")

        result_count = 0

        chunks = self._chunk_events(events)
        logger.info("Pushing {0} records to intake with index {1}".format(len(events), index))

        async with self.session() as session:
            for chunk_index, chunk in enumerate(chunks):
                request_body = {
                    "intake_key": self.configuration.intake_key,
                    "jsons": chunk,
                }

                for attempt in self._retry():
                    with attempt:
                        async with session.post(
                            batch_api,
                            headers={"User-Agent": self._connector_user_agent},
                            json=request_body,
                        ) as response:
                            if response.status >= 300:
                                error = await response.text()
                                error_message = f"Chunk {chunk_index} error: {error}"
                                exception = RuntimeError(error_message)

                                self.log_exception(exception)

                                raise exception

                            result = await response.json()

                            result_count += len(result.get("event_ids", []))
        logger.info("Push to intake completed with index {0}".format(index))

        return result_count

    async def get_events(self) -> tuple[int, datetime]:
        """
        Collects events from platform and push to intakes.

        Returns:
            list[int, datetime]:
        """
        end_date = datetime.utcnow()
        start_date = self.last_event_date

        token = None
        continue_processing = True

        data_to_push: list[dict[str, str]] = []
        result = 0
        previous_latest_date: datetime = start_date

        logger.info("Start processing: start date is {0}".format(previous_latest_date))

        while continue_processing:
            continue_processing, token, file_name = await self.broadcom_cloud_swg_client.get_report_sync(
                start_date=previous_latest_date,
                end_date=end_date,
                token=token,
            )

            logger.info(
                "Continue broadcom processing {0}. Previous latest date is {1}".format(
                    continue_processing, previous_latest_date
                )
            )

            try:
                temp_directory, unzipped_files = await file_utils.unzip(file_name)
            except BadZipFile:  # pragma: no cover
                logger.info("Empty zip file. No data to process")

                return result, previous_latest_date

            try:
                # We truncate all events that might have datetime lower then filter datetime in request
                latest_date = previous_latest_date
                for file_name in unzipped_files:
                    async with aiofiles.open(file_name) as file:
                        headers = None
                        coroutines_list: list[Coroutine[Any, Any, int]] = []
                        async for line in file:
                            if line.startswith("#") and headers is None:
                                headers = BroadcomCloudSwgClient.parse_string_as_headers(line)

                                if headers:  # pragma: no cover
                                    logger.info("Headers for current log: {0}".format(" ".join(headers)))
                            else:
                                line_as_dict = BroadcomCloudSwgClient.parse_input_string(line, headers)

                                line_date_time = BroadcomCloudSwgClient.get_date_time_from_data(line_as_dict)

                                if line_date_time:  # pragma: no cover
                                    if line_date_time < previous_latest_date:
                                        continue

                                    if latest_date < line_date_time:
                                        latest_date = line_date_time

                                data_to_push.append(line_as_dict)
                                # data_to_push = BroadcomCloudSwgClient.reduce_list(data_to_push)
                                if len(data_to_push) >= self.configuration.chunk_size:  # pragma: no cover
                                    coroutines_list.append(
                                        self.push_broadcom_data_to_intakes(
                                            [orjson.dumps(event).decode("utf-8") for event in data_to_push],
                                            len(coroutines_list) + 1,
                                        )
                                    )

                                    data_to_push = []

                                if len(coroutines_list) > int(os.getenv("PUSH_DATA_TO_INTAKES_COUNT", 100)):
                                    result += reduce(
                                        lambda x, y: x + y, list(await asyncio.gather(*coroutines_list)), 0
                                    )
                                    coroutines_list = []

                    result += reduce(lambda x, y: x + y, list(await asyncio.gather(*coroutines_list)), 0)
                    result += await self.push_broadcom_data_to_intakes(
                        [orjson.dumps(event).decode("utf-8") for event in data_to_push], 0
                    )

                    data_to_push = []

                # We update previous_latest_date because we might continue processing events in next iteration
                # so request should filter logs based on this datetime
                previous_latest_date = latest_date
            except Exception as e:  # pragma: no cover
                logger.error("Exception during processing: {}".format(str(e)))

                await file_utils.cleanup_resources([temp_directory], [file_name, *unzipped_files])

                raise e

            await file_utils.cleanup_resources([temp_directory], [file_name, *unzipped_files])

        # After processing finish we update latest event date with what we found in records
        # Se we use `previous_latest_date` as after processing it should contain the latest event datetime
        with self.context as cache:  # pragma: no cover
            logger.info(
                "New last event date now is {last_event_date}",
                last_event_date=previous_latest_date.isoformat(),
            )

            cache["last_event_date"] = previous_latest_date.isoformat()

        return result, previous_latest_date

    def run(self) -> None:  # pragma: no cover
        """Runs BroadcomCloudSwgConnector."""
        while self.running:
            try:
                loop = asyncio.get_event_loop()

                while self.running:
                    processing_start = time.time()

                    result_count, last_event_date = loop.run_until_complete(self.get_events())
                    processing_end = time.time()

                    EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(
                        processing_end - last_event_date.timestamp()
                    )

                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(result_count)

                    log_message = "No records to forward"
                    if result_count > 0:
                        log_message = "Pushed {0} records".format(result_count)

                    logger.info(log_message)
                    self.log(message=log_message, level="info")

                    FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                        last_event_date.timestamp() - processing_start
                    )

                    if result_count > 0:
                        self.log(message="Pushed {0} records".format(result_count), level="info")
                    else:
                        self.log(message="No records to forward", level="info")
                        time.sleep(self.configuration.frequency)

            except Exception as error:
                logger.error("Error while running BroadcomCloudSwgConnector: {error}", error=error)
                self.log_exception(error, message="Failed to forward events")
