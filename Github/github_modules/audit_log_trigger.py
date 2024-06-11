"""This module fetches audit logs from the Github API and pushes them to the intake."""

import asyncio
import time
import traceback
from typing import Any, Optional

import orjson
from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from github_modules import GithubModule
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


class AuditLogConnector(AsyncConnector):
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

        current_lag: int = 0
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

                await self.push_data_to_intakes(events=batch_of_events)

                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )

                # compute the lag
                now = time.time()
                current_lag = int(now - self.last_ts / 1000)
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

        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        logger.debug(f"Fetched and forwarded events in {batch_duration} seconds")
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            logger.info(f"Next batch in the future. Waiting {delta_sleep} seconds")
            await asyncio.sleep(delta_sleep)

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
