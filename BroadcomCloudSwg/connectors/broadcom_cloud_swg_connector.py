"""Contains connector, configuration and module."""

import asyncio
import os
import time
from asyncio import Queue
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cached_property, reduce
from typing import Any, AsyncGenerator, Optional

import orjson
import pytz
from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from dateutil.parser import isoparse
from loguru import logger
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.aio.helpers.files.utils import delete_file
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


@dataclass
class DatetimeRange(object):

    start_date: datetime | None = None
    end_date: datetime | None = None

    @cached_property
    def utc_start_date(self) -> datetime | None:
        if self.start_date and self.start_date.tzinfo != pytz.utc:
            return self.start_date.astimezone(pytz.utc)

        return self.start_date

    @cached_property
    def utc_end_date(self) -> datetime | None:
        if self.end_date and self.end_date.tzinfo != pytz.utc:
            return self.end_date.astimezone(pytz.utc)

        return self.end_date

    def contains(self, value: datetime) -> bool:
        _value = value
        if _value.tzinfo != pytz.utc:
            _value.astimezone(pytz.utc)

        if self.utc_end_date and self.utc_start_date and self.utc_start_date < _value < self.utc_end_date:
            return True

        if self.utc_start_date and self.utc_end_date is None and self.utc_start_date < _value:
            return True

        if self.utc_end_date and self.utc_start_date is None and self.utc_end_date > _value:
            return True

        return False

    def update_with(self, value: datetime) -> "DatetimeRange":
        _value = value
        if value.tzinfo != pytz.utc:
            _value = _value.astimezone(pytz.utc)

        new_end_date = _value
        if self.utc_end_date and self.utc_end_date > new_end_date:
            new_end_date = self.utc_end_date

        new_start_date = _value
        if self.utc_start_date and self.utc_start_date < new_start_date:
            new_start_date = self.utc_start_date

        return DatetimeRange(
            start_date=new_start_date + timedelta(microseconds=1), end_date=new_end_date - timedelta(microseconds=1)
        )

    def duplicate(self) -> "DatetimeRange":
        return DatetimeRange(start_date=self.start_date, end_date=self.end_date)

    def to_dict(self) -> dict[str, str]:
        result = {}
        if self.utc_start_date:
            result["start_date"] = self.utc_start_date.isoformat()

        if self.utc_end_date:
            result["end_date"] = self.utc_end_date.isoformat()

        return result

    @staticmethod
    def from_dict(value: dict[str, str]) -> "DatetimeRange":
        _end_parsed = None
        _start_parsed = None
        if value.get("start_date"):
            _start_parsed = isoparse(value["start_date"])
            if _start_parsed.tzinfo != pytz.utc:
                _start_parsed.astimezone(pytz.utc)

        if value.get("end_date"):
            _end_parsed = isoparse(value["end_date"])
            if _end_parsed.tzinfo != pytz.utc:
                _end_parsed.astimezone(pytz.utc)

        return DatetimeRange(start_date=_start_parsed, end_date=_end_parsed)


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
    def get_latest_offsets(self) -> dict[int, DatetimeRange]:
        offsets = {}

        with self.context as cache:
            last_event_date_str = cache.get("last_event_date")

            if last_event_date_str is not None:
                last_event_date = isoparse(last_event_date_str)
                if last_event_date.tzinfo != pytz.utc:
                    last_event_date = last_event_date.astimezone(pytz.utc)

                file_id = int(last_event_date.replace(minute=0, second=0, microsecond=0).timestamp()) * 1000
                date_range = DatetimeRange(start_date=None, end_date=last_event_date)
                offsets = {file_id: date_range}

            current_offsets: dict[str, dict[str, str]] = cache.get("offsets", {})
            offsets = {
                **offsets,
                **{int(key): DatetimeRange.from_dict(value) for key, value in current_offsets.items()},
            }

        return offsets

    def update_latest_offsets(self, offsets: dict[int, DatetimeRange]) -> None:
        logger.info("Updating offsets with {0}".format(offsets))

        current_time = datetime.utcnow().replace(minute=0, second=0, microsecond=0).timestamp() * 1000
        delta = int(timedelta(hours=1).total_seconds()) * 1000

        # Save offsets for last 24 hours for debug purposed
        result = {str(key): value.to_dict() for key, value in offsets.items() if key > current_time - delta * 24}

        with self.context as cache:
            cache["last_event_date"] = None
            cache["offsets"] = result

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
            rate_limiter=AsyncLimiter(1, 5),  # 1 request per 5 seconds for external API
        )

        return self._broadcom_cloud_swg_client

    async def consume_file_events(self, queue: Queue[dict[str, str] | None], tag: str | None = None) -> int:
        """
        Consumer function for specified queue with optional index of consumer.

        Tag is used only to determine consumer name.

        Provides total amount of messages that where pushed to intake.

        Args:
            queue: Queue[dict[str, str] | None]
            tag: str | None = None

        Returns:
            int:
        """
        consumer_name = tag if tag and tag != "" else "Consumer[0]"

        data_to_push: list[dict[str, str]] = []
        result = 0

        while True:
            item = await queue.get()
            queue.task_done()

            # It means that producer finished with producing messages.
            if item is None:
                break

            data_to_push.append(item)

            if len(data_to_push) >= self.configuration.chunk_size:  # pragma: no cover
                result += len(
                    await self.push_data_to_intakes(
                        [orjson.dumps(event).decode("utf-8") for event in data_to_push if event != {}]
                    )
                )

                logger.debug(
                    "{0}: New batch with events pushed to intake. Total processed events {1}".format(
                        consumer_name, result
                    )
                )

                data_to_push = []

        result += len(
            await self.push_data_to_intakes(
                [orjson.dumps(event).decode("utf-8") for event in data_to_push if event != {}]
            )
        )

        logger.info("{0}: Stop getting new messages. Total events pushed to intake {1}".format(consumer_name, result))

        return result

    @staticmethod
    async def produce_file_to_queue(
        file_path: str, queue: Queue[dict[str, str] | None], date_range: DatetimeRange, consumers_count: int = 1
    ) -> DatetimeRange:
        """
        Reads zipped archive line by line and produce parsed messages to queue.

        As result after producing we get new lowest and highest datetime.

        Args:
            file_path: str
            queue: Queue
            consumers_count: int
            date_range: DatetimeRange

        Returns:
            DatetimeRange:
        """
        headers = None
        total_produced = 0
        total_skipped = 0

        new_date_time_range: DatetimeRange = date_range.duplicate()

        logger.info(
            """
                File {0}: Start producing data. Should skip all events that does not match criteria:
                    * Event datetime should be lower then {1}
                    * Event datetime should be higher then {2}
                Current datetime in utc is: {3}
            """.format(
                file_path,
                new_date_time_range.utc_start_date,
                new_date_time_range.utc_end_date,
                datetime.now(pytz.utc),
            )
        )

        try:
            async for line in file_utils.read_zip_lines(file_path):
                if line.startswith("#") and headers is None:
                    headers = BroadcomCloudSwgClient.parse_string_as_headers(line)

                    if headers:  # pragma: no cover
                        logger.debug("File {0}: Headers for current log file: {0}".format(" ".join(headers)))
                else:
                    line_as_dict = BroadcomCloudSwgClient.parse_input_string(line, headers)

                    # Bug: sometimes it does not have correct direction based on date time
                    event_date = BroadcomCloudSwgClient.get_date_time_from_data(line_as_dict)

                    if event_date:
                        if date_range.contains(event_date):
                            total_skipped += 1
                            continue

                        new_date_time_range = new_date_time_range.update_with(event_date)

                    await queue.put(line_as_dict)
                    total_produced += 1

        except Exception as e:  # pragma: no cover
            logger.error("File {0}: Error during zip file processing: {1}".format(file_path, str(e)))

        # Before pushing to queue None we should wait until all messages in queue are processed
        await queue.join()

        logger.info(
            "File {0}: Finished to produce events. Total produced: {1}. Total skipped: {2} ".format(
                file_path,
                total_produced,
                total_skipped,
            )
        )

        for _ in range(0, consumers_count):
            # We will push None for each consumer based on their count
            await queue.put(None)

        return new_date_time_range

    async def process_datetime(
        self, date_to_process: datetime, date_range: DatetimeRange | None = None
    ) -> tuple[int, DatetimeRange, int]:
        """
        Processing datetime with applying date range filter.

        Args:
            date_to_process:
            date_range:

        Returns:
            tuple[int, DatetimeRange, int]:
        """
        current_date = datetime.now(pytz.utc)
        _date_to_process = date_to_process.replace(minute=0, second=0, microsecond=0)
        if _date_to_process.tzinfo != pytz.utc:
            _date_to_process.astimezone(pytz.utc)

        file_id = int(_date_to_process.timestamp()) * 1000

        _date_range = date_range or DatetimeRange(
            start_date=_date_to_process + timedelta(hours=1), end_date=_date_to_process
        )

        updated_date_time_range = _date_range.duplicate()

        local_file_name: str | None = None
        total_processed_events = 0

        try:
            if (current_date - _date_to_process) > timedelta(hours=2):
                result = await self.broadcom_cloud_swg_client.list_of_files(
                    _date_to_process - timedelta(hours=2),
                    _date_to_process,
                )

                logger.info(
                    "List of files is {0}. Trying to find {1} (file id is {2})".format(
                        result, _date_to_process, file_id
                    )
                )

                is_available = False

                for data in result.get("items", []):
                    if int(data.get("date", 0)) == file_id:
                        is_available = True

                if is_available:
                    local_file_name = await self.broadcom_cloud_swg_client.download_file(file_id)

            else:
                local_file_name, _ = await self.broadcom_cloud_swg_client.get_near_realtime_report(_date_to_process)

        except Exception as e:
            logger.error(
                """
                    Error while getting file:
                     Date: {0}
                     File id: {1}
                     Offsets: {2}
                     Exception: {3}
                """.format(
                    date_to_process, file_id, _date_range, e
                )
            )

        if local_file_name is not None:
            logger.info("File {0}: Start to decompress and process zip file".format(local_file_name))

            queue: Queue[dict[str, str] | None] = Queue()
            consumers_amount = int(os.getenv("BROADCOM_CONSUMERS_COUNT", 4))
            processed_result: Any = await asyncio.gather(
                self.produce_file_to_queue(local_file_name, queue, DatetimeRange(), consumers_amount),
                *[
                    self.consume_file_events(queue, "{0}: Consumer[{1}]".format(local_file_name, i))
                    for i in range(1, consumers_amount)
                ],
            )

            updated_date_time_range = processed_result[0]
            list_of_ids: list[int] = list(processed_result[1:])
            total_processed_events = reduce(lambda x, y: x + y, list_of_ids, 0)

            logger.info(
                """
                    Processing large zip file {0} result:
                        lowest date: {1}
                        latest date: {2}
                    Total events: {3}
                """.format(
                    local_file_name,
                    updated_date_time_range.utc_start_date,
                    updated_date_time_range.utc_end_date,
                    total_processed_events,
                )
            )

            await delete_file(local_file_name)

        return file_id, updated_date_time_range, total_processed_events

    async def get_events(self) -> tuple[int, datetime]:
        """
        Collects events from platform and push to intakes.

        Returns:
            tuple[int, datetime]:
        """
        current_date = datetime.now(pytz.utc)
        current_file = int(current_date.replace(minute=0, second=0, microsecond=0).timestamp()) * 1000
        delta = int(timedelta(hours=1).total_seconds()) * 1000

        one_hour_ago = current_file - delta
        two_hours_ago = one_hour_ago - delta

        offsets = self.get_latest_offsets

        result: list[tuple[int, DatetimeRange, int]] = list()

        for file_id in [two_hours_ago, one_hour_ago]:
            file_date_range = offsets.get(file_id)
            if file_date_range is not None:
                process_result = await self.process_datetime(
                    datetime.fromtimestamp(file_id / 1000, pytz.utc), file_date_range
                )
                self.update_latest_offsets({**offsets, process_result[0]: process_result[1]})
                result.append(process_result)

        process_result = await self.process_datetime(
            datetime.fromtimestamp(current_file / 1000, pytz.utc), offsets.get(current_file)
        )
        self.update_latest_offsets({**offsets, process_result[0]: process_result[1]})
        result.append(process_result)

        # #
        # tasks: list[Coroutine[Any, Any, tuple[int, DatetimeRange, int]]] = [
        #     self.process_datetime(datetime.fromtimestamp(current_file / 1000, pytz.utc), offsets.get(current_file))
        # ]
        #
        # for file_id in [one_hour_ago, two_hours_ago]:
        #     file_date_range = offsets.get(file_id)
        #     if file_date_range is not None:
        #         tasks.append(self.process_datetime(datetime.fromtimestamp(file_id / 1000, pytz.utc), file_date_range))
        #
        # result: list[tuple[int, DatetimeRange, int]] = list(await asyncio.gather(*tasks))

        total_events = int(sum([data[2] for data in result]))

        return total_events, datetime.now(pytz.utc)

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

                    FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                        last_event_date.timestamp() - processing_start
                    )

                    if result_count > 0:
                        self.log(message="Total forwarded {0} records".format(result_count), level="info")
                    else:
                        self.log(message="No records to forward", level="info")
                        time.sleep(self.configuration.frequency)

            except Exception as error:
                self.log_exception(error, message="Error while running BroadcomCloudSwgConnector")
                time.sleep(self.configuration.frequency)
