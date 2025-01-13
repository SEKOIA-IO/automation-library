import asyncio
import json
import os
import signal
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from functools import cached_property

from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import Connector

from office365.metrics import FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS

from .checkpoint import Checkpoint
from .configuration import Office365Configuration
from .errors import FailedToActivateO365Subscription
from .helpers import split_date_range
from .office365_client import Office365API


class Office365Connector(AsyncConnector):
    configuration: Office365Configuration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.limit_of_events_to_push = int(os.getenv("OFFICE365_BATCH_SIZE", 10000))
        self.frequency = int(os.getenv("OFFICE365_PULL_FREQUENCY", 60))
        self.time_range_interval = int(os.getenv("OFFICE365_TIME_RANGE_INTERVAL", 30))

    async def shutdown(self) -> None:
        """
        Shutdown the connector
        """
        super(Connector, self).stop()
        if self._session and not self._session.closed:
            await self._session.close()

    @cached_property
    def client(self) -> Office365API:
        """Office365 API client

        Returns: An instance of the client
        """
        return Office365API(
            client_id=str(self.configuration.client_id),
            client_secret=self.configuration.client_secret,
            tenant_id=self.configuration.tenant_id,
        )

    async def pull_content(self, start_date: datetime, end_date: datetime) -> AsyncGenerator[list[str], None]:
        """Pulls content from Office 365 subscriptions

        Args:
            start_date (datetime): Start date of the interval
            end_date (datetime): End date of the interval

        Returns:
            list[dict]: List of events recevied for the interval
        """
        pulled_events: list[str] = []

        content_types = await self.client.list_subscriptions()
        for content_type in content_types:
            # Get the paginated contents from a subscription
            async for contents in self.client.get_subscription_contents(
                content_type, start_time=start_date, end_time=end_date
            ):
                for content in contents:
                    events = await self.client.get_content(content["contentUri"])
                    for event in events:
                        pulled_events.append(json.dumps(event))

                    if len(pulled_events) > self.limit_of_events_to_push:
                        yield pulled_events
                        pulled_events = []

        if len(pulled_events) > 0:
            yield pulled_events

    async def send_events(self, events: list[str]):
        """Sends event to Sekoia intake

        Args:
            events (list[dict]): Events to forward to intake
        """
        self.log(f"Pushing {len(events)} event(s) to intake", level="info")
        OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(events))

        await self.push_data_to_intakes(events=events)

    async def activate_subscriptions(self):
        """Activates an Office 365 subscriptions"""
        try:
            await self.client.activate_subscriptions()
        except FailedToActivateO365Subscription as exp:
            self.log_exception(
                exception=exp,
                message="An exception occurred when trying to subscribe to Office365 events.",
            )

    async def forward_next_batches(self, checkpoint: Checkpoint):
        start_time = time.time()
        start_pull_date = checkpoint.offset
        end_pull_date = datetime.now(UTC)

        for start_date, end_date in split_date_range(
            start_pull_date, end_pull_date, timedelta(minutes=self.time_range_interval)
        ):
            intermediate_start_time = time.time()

            # Get events for the current date range
            async for list_of_events in self.pull_content(start_date, end_date):
                await self.send_events(list_of_events)

            # get the ending time and compute the duration to forward the events
            intermediate_end_time = time.time()
            intermediate_batch_duration = intermediate_end_time - intermediate_start_time
            FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                intermediate_batch_duration
            )

            # save intermediate end date
            checkpoint.offset = end_date

        # get the ending time and compute the duration to forward the events
        end_time = time.time()
        batch_duration = end_time - start_time

        # save end date
        checkpoint.offset = end_pull_date

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.frequency - batch_duration
        if delta_sleep > 0:
            await asyncio.sleep(delta_sleep)

    async def forward_events_forever(self, checkpoint: Checkpoint):
        while self.running:
            await self.forward_next_batches(checkpoint)

    async def collect_events(self):
        await self.activate_subscriptions()

        checkpoint = Checkpoint(self._data_path, self.configuration.intake_key)

        while self.running:
            try:
                await self.forward_events_forever(checkpoint)

            except Exception as error:
                self.log_exception(error, message="Failed to forward events")

        await self.client.close()

    def run(self):  # pragma: no cover
        """Main execution thread

        It starts by creating and launching the clear_cache subthread
        Activate subscriptions
        Then loop every 60 seconds, pull events using the Office 365 API and forward them.
        When stopped, the clear_cache is stopped and joined as well so that we wait for it to end gracefully.
        """
        self.log(message="Office365 Trigger has started", level="info")

        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGTERM, lambda: loop.create_task(self.shutdown()))
        loop.add_signal_handler(signal.SIGINT, lambda: loop.create_task(self.shutdown()))
        loop.run_until_complete(self.collect_events())

        self.log(message="Office365 Trigger has stopped", level="info")
