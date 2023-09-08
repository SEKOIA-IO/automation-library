"""This module fetches audit logs from the Github API and pushes them to the intake."""
import asyncio
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator, Optional
from urllib.parse import urljoin

import orjson
from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from pydantic import BaseModel, Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.module import Module
from sekoia_automation.storage import PersistentJSON

from github_modules.async_client.http_client import AsyncGithubClient
from github_modules.logging import get_logger
from github_modules.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS

logger = get_logger()


class AuditLogConnectorConfiguration(DefaultConnectorConfiguration):
    """Connector configuration for Github audit logs."""

    frequency: int = 1
    timebuffer: int = 60000
    ratelimit_per_minute: int = 83
    filter: str | None = None
    q: str | None = None


class GithubModuleConfiguration(BaseModel):
    """Contains all necessary configuration to interact with Github API."""

    org_name: str = Field(description="The name of your Github organization")
    apikey: str | None = Field(
        default=None, required=False, secret=True, description="The APIkey to authenticate call to the Github API"
    )
    pem_file: str | None = Field(
        default=None, required=False, secret=True, description="Pem file to interact with Github API"
    )
    app_id: int | None = Field(default=None, required=False, description="Github app id to interact with Github API")


class GithubModule(Module):
    """Configuration for Github module."""

    configuration: GithubModuleConfiguration


class AuditLogConnector(Connector):
    """This connector fetches audit logs from the Github API"""

    _github_client: AsyncGithubClient | None = None

    _session: ClientSession | None = None
    _rate_limiter: AsyncLimiter | None = None

    module: GithubModule
    configuration: AuditLogConnectorConfiguration

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """
        Initialize connector and load the context

        Args:
            args: Any
            kwargs: Optional[Any]
        """
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

    @property
    def github_client(self) -> AsyncGithubClient:
        """
        Get async github client.

        Returns:
            AsyncGithubClient:
        """
        if self._github_client is not None:
            return self._github_client

        rate_limiter = AsyncLimiter(self.configuration.ratelimit_per_minute)

        self._github_client = AsyncGithubClient(
            organization=self.module.configuration.org_name,
            api_key=self.module.configuration.apikey,
            pem_file=self.module.configuration.pem_file,
            app_id=self.module.configuration.app_id,
            rate_limiter=rate_limiter,
        )

        return self._github_client

    @classmethod
    def rate_limiter(cls) -> AsyncLimiter:  # pragma: no cover
        """
        Get or initialize rate limiter.

        Returns:
            AsyncLimiter:
        """
        if cls._rate_limiter is None:
            cls._rate_limiter = AsyncLimiter(1, 1)

        return cls._rate_limiter

    @classmethod
    @asynccontextmanager
    async def session(cls) -> AsyncGenerator[ClientSession, None]:  # pragma: no cover
        """
        Get or initialize client session.

        Returns:
            ClientSession:
        """
        if cls._session is None:
            cls._session = ClientSession()

        async with cls.rate_limiter():
            yield cls._session

    @property
    def last_ts(self) -> int:
        """
        Get last timestamp to start fetch events from.

        Returns:
            int:
        """
        with self.context as cache:
            ts = cache.get("last_ts")

            if ts is None:
                result = round(time.time() * 1000) - self.configuration.timebuffer
                self.last_ts = result
            else:
                result = int(ts)

            return result

    @last_ts.setter
    def last_ts(self, last_ts: int) -> None:
        """
        Set last timestamp to start fetch events from.

        Args:
            last_ts: int
        """
        with self.context as cache:
            cache["last_ts"] = str(last_ts)

    def stop(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """
        Stops the connector with additional log message.

        Args:
            args: Any
            kwargs: Optional[Any]
        """

        self.log(message="Stopping Github audit logs connector", level="info")
        # Exit signal received, asking the processor to stop
        super().stop(args, kwargs)

    async def _push_data_to_intake(self, events: list[str]) -> list[str]:  # pragma: no cover
        """
        Custom method to push events to intakes.

        Args:
            events: list[str]

        Returns:
            list[str]:
        """
        self._last_events_time = datetime.utcnow()
        batch_api = urljoin(self.configuration.intake_server, "/batch")

        logger.info("Pushing total: {count} events to intakes", count=len(events))

        result_ids = []

        chunks = self._chunk_events(events, self.configuration.chunk_size)
        headers = {"User-Agent": f"sekoiaio-connector-{self.configuration.intake_key}"}
        async with self.session() as session:
            for chunk_index, chunk in enumerate(chunks):
                logger.info(
                    "Start to push chunk {chunk_index} with data count {data_count} to intakes",
                    chunk_index=chunk_index,
                    data_count=len(chunk),
                )
                request_body = {"intake_key": self.configuration.intake_key, "jsons": chunk}

                async with session.post(batch_api, headers=headers, json=request_body) as response:
                    # Not sure what response code will be at this point to identify error.
                    # Usually 200, 201, 202 ... until 300 means success
                    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Status#successful_responses
                    if response.status >= 300:
                        error = await response.text()
                        logger.error(
                            "Error while pushing chunk {chunk_index} to intakes: {error}",
                            chunk_index=chunk_index,
                            error=error,
                        )

                        raise Exception(error)

                    logger.info(
                        "Successfully pushed chunk {chunk_index} to intakes",
                        chunk_index=chunk_index,
                    )
                    result = await response.json()
                    result_ids.extend(result.get("event_ids", []))

        return result_ids

    async def get_audit_events(self, last_ts: int) -> list[dict[str, Any]]:
        """
        Get audit events from Github API.

        Args:
            last_ts: int
        """
        return await self.github_client.get_audit_logs(start_from=last_ts)

    def _refine_batch(self, batch: list[dict[str, Any]], batch_start_time: float) -> list[dict[str, Any]]:
        """
        Remove events that are in the time buffer.

        As we get events in asc ordering ( by date ) we can stop the loop when we reach the time buffer.

        Args:
            batch: list[dict[str, Any]]
            batch_start_time: float

        Returns:
            list[dict[str, Any]]:
        """
        for index, event in enumerate(batch):
            if event["@timestamp"] > int((batch_start_time * 1000) - self.configuration.timebuffer):
                return batch[0:index]

        return batch

    async def next_batch(self) -> None:
        """Fetches the next batch of events and pushes them to the intake."""

        batch_start_time = time.time()
        audit_events = await self.get_audit_events(self.last_ts)
        INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(audit_events))

        if type(audit_events) is list:
            filtered_data = self._refine_batch(audit_events, batch_start_time)

            # if the response is not empty, push it
            if filtered_data:
                self.last_ts = filtered_data[-1]["@timestamp"]
                batch_of_events = [orjson.dumps(event).decode("utf-8") for event in filtered_data]
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))

                await self._push_data_to_intake(events=batch_of_events)

                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )

                # compute the lag
                now = time.time()
                current_lag = now - self.last_ts / 1000
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).observe(int(current_lag))
            else:
                self.log(
                    message="No events to forward ",
                    level="info",
                )
        else:
            self.log(
                message=str(audit_events),
                level="warn",
            )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        logger.debug(f"Fetched and forwarded events in {batch_duration} seconds")
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            logger.debug(f"Next batch in the future. Waiting {delta_sleep} seconds")
            time.sleep(delta_sleep)

    def run(self) -> None:  # pragma: no cover
        """Runs Github audit logs."""

        self.log(message="Start fetching Github audit logs", level="info")

        while self.running:
            try:
                loop = asyncio.get_event_loop()

                while self.running:
                    loop.run_until_complete(self.next_batch())

            except Exception as error:
                traceback.print_exc()
                self.log_exception(error, message="Failed to forward events")
