import asyncio
import time
from datetime import timedelta
from typing import Any, Optional

import orjson
from cachetools import Cache, LRUCache
from dateutil.parser import isoparse
from loguru import logger
from pydantic import Field
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.module import Module

from connectors.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS
from graph_api.client import GraphAPIError, GraphAuditClient


class AzureEntraIdGraphApiConnectorConfig(DefaultConnectorConfiguration):
    """Connector configuration."""

    tenant_id: str
    client_id: str
    client_secret: str = Field(secret=True)
    frequency: int = 60
    chunk_size: int = 1000


class AzureEntraIdGraphApiConnector(AsyncConnector):
    module: Module
    configuration: AzureEntraIdGraphApiConnectorConfig

    _client: GraphAuditClient | None = None

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        super().__init__(*args, **kwargs)
        self.last_event_date_signin = CheckpointDatetime(
            path=self.data_path,
            start_at=timedelta(days=7),
            ignore_older_than=timedelta(days=7),
            subkey="signin_datetime",
        )

        self.last_event_date_directory = CheckpointDatetime(
            path=self.data_path,
            start_at=timedelta(days=7),
            ignore_older_than=timedelta(days=7),
            subkey="directory_datetime",
        )

        self.signin_cache = self.load_cache("signin", maxsize=500)
        self.directory_alers = self.load_cache("directory", maxsize=500)

    def load_cache(self, key: str, maxsize: int) -> Cache[str, bool]:
        context = self.last_event_date_signin._context if key == "signin" else self.last_event_date_directory._context
        result: LRUCache[str, bool] = LRUCache(maxsize=maxsize)

        with context as cache:
            events_ids = cache.get(key, [])

        for event_id in events_ids:
            result[event_id] = True

        return result

    def persist_cache(self, key: str) -> None:
        context = self.last_event_date_signin._context if key == "signin" else self.last_event_date_directory._context
        cache = self.signin_cache if key == "signin" else self.directory_alers

        with context as ctx:
            ctx[key] = list(cache.keys())

    @property
    def client(self) -> GraphAuditClient:
        if not self._client:
            self._client = GraphAuditClient(
                tenant_id=self.configuration.tenant_id,
                client_id=self.configuration.client_id,
                client_secret=self.configuration.client_secret,
            )

        return self._client

    def stop(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """
        Stop the connector.

        Temporary redefine the method to avoid known SDK issues.
        """
        super(Connector, self).stop(*args, **kwargs)

    async def run_directory(self) -> int:
        events = []
        total_events = 0
        new_offset = self.last_event_date_directory.offset
        async for event in self.client.list_directory_audits(start=self.last_event_date_directory.offset):
            if not self.running:
                break

            if event["id"] in self.directory_alers:
                continue

            events.append(event)
            if len(events) >= self.configuration.chunk_size:
                total_events += len(
                    await self.push_data_to_intakes([orjson.dumps(event).decode() for event in events])
                )
                for data in events:
                    new_offset = max(new_offset, isoparse(data["activityDateTime"]))
                    self.directory_alers[data["id"]] = True
                self.last_event_date_directory.offset = new_offset
                self.persist_cache("directory")
                events = []

        if events:
            total_events += len(await self.push_data_to_intakes([orjson.dumps(event).decode() for event in events]))
            for data in events:
                new_offset = max(new_offset, isoparse(data["activityDateTime"]))
                self.directory_alers[data["id"]] = True
            self.last_event_date_directory.offset = new_offset
            self.persist_cache("directory")

        return total_events

    async def run_signin(self) -> int:
        events = []
        total_events = 0
        new_offset = self.last_event_date_directory.offset
        async for event in self.client.list_signins(start=self.last_event_date_directory.offset):
            if not self.running:
                break

            if event["id"] in self.directory_alers:
                continue

            events.append(event)
            if len(events) >= self.configuration.chunk_size:
                total_events += len(
                    await self.push_data_to_intakes([orjson.dumps(event).decode() for event in events])
                )
                for data in events:
                    new_offset = max(new_offset, isoparse(data["createdDateTime"]))
                    self.directory_alers[data["id"]] = True
                self.last_event_date_directory.offset = new_offset
                self.persist_cache("signin")
                events = []

        if events:
            total_events += len(await self.push_data_to_intakes([orjson.dumps(event).decode() for event in events]))
            for data in events:
                new_offset = max(new_offset, isoparse(data["createdDateTime"]))
                self.directory_alers[data["id"]] = True
            self.last_event_date_directory.offset = new_offset
            self.persist_cache("signin")

        return total_events

    async def single_run(self) -> int:
        directory_results = await self.run_directory()
        signin_results = await self.run_signin()

        return directory_results + signin_results

    async def async_run(self) -> None:  # pragma: no cover
        while self.running:
            try:
                processing_start = time.time()
                result = await self.single_run()
                last_event_date_signin = self.last_event_date_signin.offset
                last_event_date_directory = self.last_event_date_directory.offset
                last_event_date = max(last_event_date_signin, last_event_date_directory)
                processing_end = time.time()

                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(
                    processing_end - last_event_date.timestamp()
                )

                log_message = "No records to forward"
                if result > 0:
                    log_message = "Pushed {0} records".format(result)

                self.log(message=log_message, level="info")
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(result)

                processing_time = processing_end - processing_start
                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(processing_time)
                logger.info(
                    "Processing took {processing_time} seconds",
                    processing_time=processing_time,
                )

                if result == 0:
                    await asyncio.sleep(self.configuration.frequency)

            except GraphAPIError as error:
                # In case if we handle the server custom error we should raise critical message and then sleep.
                # This will help to stop the connector in case if credentials are invalid or permissions denied.
                self.log(message=str(error), level="critical")
                await asyncio.sleep(self.configuration.frequency)

            except TimeoutError:
                self.log(message="A timeout was raised by the client", level="warning")
                await asyncio.sleep(self.configuration.frequency)

            except Exception as error:
                self.log_exception(error)
                await asyncio.sleep(self.configuration.frequency)

        await self.client.close()
        if self._session:
            await self._session.close()

    def run(self) -> None:  # pragma: no cover
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_run())
