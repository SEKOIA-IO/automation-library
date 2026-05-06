import asyncio
import json
import os
import signal
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from functools import cached_property

import aiohttp
from sekoia_automation.aio.connector import AsyncConnector

from office365.metrics import (
    AUTH_FAILURES,
    FORWARD_EVENTS_DURATION,
    NETWORK_FAILURES,
    O365_API_FAILURES,
    OUTCOMING_EVENTS,
)

from .checkpoint import Checkpoint
from .configuration import Office365Configuration
from .error_handling import FailureTracker
from .errors import (
    ApplicationAuthenticationFailed,
    FailedToActivateO365Subscription,
    FailedToGetO365AuditContent,
    FailedToGetO365SubscriptionContents,
    FailedToListO365Subscriptions,
)
from .helpers import split_date_range
from .office365_client import Office365API

AUTH_RECOVERY_SLEEP_MULTIPLIER = 10
MAX_RECOVERY_SLEEP_SECONDS = 600
MAX_BACKOFF_EXPONENT = 5


class Office365Connector(AsyncConnector):
    configuration: Office365Configuration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.limit_of_events_to_push = int(os.getenv("OFFICE365_BATCH_SIZE", 10000))
        self._frequency = int(os.getenv("OFFICE365_PULL_FREQUENCY", 60))
        self.time_range_interval = int(os.getenv("OFFICE365_TIME_RANGE_INTERVAL", 30))
        self._auth_failures = FailureTracker()
        self._o365_failures = FailureTracker()
        self._network_failures = FailureTracker()

    async def shutdown(self) -> None:
        """
        Shutdown the connector
        """
        # Call Trigger.stop() to set stop event and stop logs timer
        # Skip Connector/AsyncConnector.stop() as they have sync issues in async context
        super().stop()

        # Close client if it exists (cached_property stores in __dict__)
        if hasattr(self, "client") and not getattr(self, "_client_closed", False):
            await self.client.close()
            self._client_closed = True

        if self._session and not self._session.closed:
            await self._session.close()

    @cached_property
    def client(self) -> Office365API:
        """Office365 API client

        Returns: An instance of the client
        """
        client = Office365API(
            client_id=str(self.configuration.client_id),
            client_secret=self.configuration.client_secret,
            tenant_id=self.configuration.tenant_id,
        )
        self._client_closed = False
        return client

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
                    # https://learn.microsoft.com/en-us/office/office-365-management-api/office-365-management-activity-api-reference
                    content_expiration = content.get("contentExpiration")

                    if content_expiration:
                        now = datetime.now(UTC)
                        parsed_expiration = datetime.strptime(content_expiration, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
                            tzinfo=UTC
                        )

                        if now > parsed_expiration:
                            continue

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

        # save end date
        checkpoint.offset = end_pull_date

    async def forward_events_forever(self, checkpoint: Checkpoint):
        while self.running:
            try:
                start_time = time.time()
                await self.forward_next_batches(checkpoint)
                self._reset_failure_trackers()
                # get the ending time and compute the duration to forward the events
                end_time = time.time()
                batch_duration = end_time - start_time
                # compute the remaining sleeping time. If greater than 0, sleep
                delta_sleep = self._frequency - batch_duration
                if delta_sleep > 0:
                    await asyncio.sleep(delta_sleep)

            except ApplicationAuthenticationFailed as error:
                await self._handle_auth_failure(error)

            except (
                FailedToListO365Subscriptions,
                FailedToGetO365SubscriptionContents,
                FailedToGetO365AuditContent,
            ) as error:
                await self._handle_o365_api_failure(error)

            except (aiohttp.ClientError, asyncio.TimeoutError) as error:
                await self._handle_network_failure(error)

            except Exception as error:
                # Unknown / programming error: keep full traceback for debugging.
                self.log_exception(error, message="Unexpected error in forwarding loop")
                await asyncio.sleep(self._frequency)

    async def _handle_auth_failure(self, error: ApplicationAuthenticationFailed) -> None:
        AUTH_FAILURES.labels(intake_key=self.configuration.intake_key).inc()
        count = self._auth_failures.record("auth")
        if self._auth_failures.should_log():
            response = error.context.get("response") or {}
            details = response.get("error_description")
            message = (
                f"Authentication against Microsoft Entra ID failed (consecutive={count})."
                " Verify client_id, client_secret and tenant_id."
            )
            if details:
                message = f"{message} Details: {details}"
            self.log(message=message, level=self._auth_failures.log_level)
        await asyncio.sleep(min(self._frequency * AUTH_RECOVERY_SLEEP_MULTIPLIER, MAX_RECOVERY_SLEEP_SECONDS))

    async def _handle_o365_api_failure(self, error: Exception) -> None:
        operation = type(error).__name__
        context = getattr(error, "context", {}) or {}
        status_code = context.get("status_code")
        error_code = context.get("error_code")

        O365_API_FAILURES.labels(
            intake_key=self.configuration.intake_key,
            status=str(status_code) if status_code is not None else "unknown",
            operation=operation,
        ).inc()

        count = self._o365_failures.record((operation, status_code, error_code))
        if self._o365_failures.should_log():
            self.log(
                message=(f"Office 365 Management API call '{operation}' failed " f"(consecutive={count}): {error}"),
                level=self._o365_failures.log_level,
            )

        await asyncio.sleep(self._compute_backoff_seconds(count))

    async def _handle_network_failure(self, error: Exception) -> None:
        exc_type = type(error).__name__
        NETWORK_FAILURES.labels(intake_key=self.configuration.intake_key, exc_type=exc_type).inc()
        count = self._network_failures.record(exc_type)
        if self._network_failures.should_log():
            self.log(
                message=f"Network error talking to Microsoft (consecutive={count}): {exc_type}: {error}",
                level=self._network_failures.log_level,
            )
        await asyncio.sleep(self._compute_backoff_seconds(count))

    def _compute_backoff_seconds(self, consecutive_count: int) -> int:
        exponent = min(max(consecutive_count - 1, 0), MAX_BACKOFF_EXPONENT)

        return min(self._frequency * (2**exponent), MAX_RECOVERY_SLEEP_SECONDS)

    def _reset_failure_trackers(self) -> None:
        for label, tracker in (
            ("authentication", self._auth_failures),
            ("Office 365 API", self._o365_failures),
            ("network", self._network_failures),
        ):
            previous = tracker.reset()
            if previous > 0:
                self.log(
                    message=f"Recovered from {label} failures after {previous} consecutive errors",
                    level="info",
                )

    async def collect_events(self):
        checkpoint = Checkpoint(self._data_path, self.configuration.intake_key)

        try:
            await self.activate_subscriptions()
            await self.forward_events_forever(checkpoint)
        finally:
            # Ensure client is closed on exit (cached_property stores in __dict__)
            if "client" in self.__dict__ and not getattr(self, "_client_closed", False):
                await self.client.close()
                self._client_closed = True

    def run(self):  # pragma: no cover
        """Main execution thread

        Runs the async event collection loop. The connector will continuously pull events
        from Office 365 Management API and forward them to Sekoia intake until stopped.
        """
        self.log(message="Office365 Trigger has started", level="info")

        loop = asyncio.get_event_loop()

        # Set up signal handlers to stop gracefully
        def handle_stop_signal():
            self.log(message="Received stop signal", level="info")
            loop.create_task(self.shutdown())

        loop.add_signal_handler(signal.SIGTERM, handle_stop_signal)
        loop.add_signal_handler(signal.SIGINT, handle_stop_signal)

        try:
            loop.run_until_complete(self.collect_events())

        except ApplicationAuthenticationFailed as auth_error:
            message = "Authentication failed. Please check your client ID, client secret and tenant ID."

            response = auth_error.context.get("response")
            if response and "error_description" in response:
                message = f"{message} Details: {response['error_description']}"

            self.log_exception(auth_error)
            self.log(message=message, level="critical")

        self.log(message="Office365 Trigger has stopped", level="info")
