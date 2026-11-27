import asyncio
import json
import os
import signal
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from functools import cached_property

from sekoia_automation.aio.connector import AsyncConnector

from office365.metrics import FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS

from .checkpoint import Checkpoint
from .configuration import Office365Configuration
from .errors import (
    GENERIC_HINT,
    FailedToActivateO365Subscription,
    FailedToActivateSomeO365Subscriptions,
    FailedToListO365Subscriptions,
    O365Exception,
    SessionClosedError,
)
from .helpers import split_date_range
from .office365_client import EXPECTED_SUBSCRIPTIONS, Office365API

# Exponential backoff (1, 2, 4... minutes, up to 1 hour) used:
# - to retry the activation of the failed subscriptions, while the active ones are collected
# - before restarting the connector after an error that prevents any collection
RETRY_MIN_DELAY = 60
RETRY_MAX_DELAY = 3600


def backoff_delay(attempt: int) -> int:
    """Delay, in seconds, before the next attempt after `attempt` failures in a row"""
    return min(RETRY_MAX_DELAY, RETRY_MIN_DELAY * 2 ** max(0, attempt - 1))


class Office365Connector(AsyncConnector):
    configuration: Office365Configuration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.limit_of_events_to_push = int(os.getenv("OFFICE365_BATCH_SIZE", 10000))
        self._frequency = int(os.getenv("OFFICE365_PULL_FREQUENCY", 60))
        self.time_range_interval = int(os.getenv("OFFICE365_TIME_RANGE_INTERVAL", 30))

        # State of the activation of the subscriptions
        self._active_content_types: set[str] = set()
        self._activation_pending = True
        self._activation_failures = 0
        self._next_activation_attempt = 0.0

    async def shutdown(self) -> None:
        """
        Shutdown the connector
        """
        # Stop the connector
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

    def _reset_client(self) -> None:
        """Drop the cached Office365API so a fresh client (and aiohttp session) is built on next access.

        Called after a SessionClosedError surfaces while the connector is still running, so the
        next request rebuilds the underlying aiohttp.ClientSession.
        """
        self.__dict__.pop("client", None)
        self._client_closed = False

    async def pull_content(
        self, start_date: datetime, end_date: datetime, content_types: list[str] | None = None
    ) -> AsyncGenerator[list[str]]:
        """Pulls content from Office 365 subscriptions

        Args:
            start_date (datetime): Start date of the interval
            end_date (datetime): End date of the interval
            content_types (list[str] | None): Active subscriptions, listed from Microsoft if not given

        Returns:
            AsyncGenerator[list[str]]: Batches of events received for the interval
        """
        pulled_events: list[str] = []

        if content_types is None:
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

    async def _activate_subscriptions(self, recover: bool = False):
        """Activates the Office 365 subscriptions, and schedules a new attempt if some of them failed

        Raises the activation error when no subscription is active, as no event can be collected:
        the connector is restarted, and stopped by the SDK if the error persists (see `run`).
        """
        try:
            active_content_types = await self.client.activate_subscriptions()
        except SessionClosedError as exp:
            if not recover:
                self.log_exception(
                    exception=exp,
                    message=(
                        "Office365 client session was closed again after recovery; "
                        "skipping subscription activation this run."
                    ),
                )
                return
            else:
                if not self.running:
                    self.log(
                        message="Skipped Office365 subscription activation: client session closed during shutdown.",
                        level="info",
                    )
                    return
                # Unexpected closure while still running: rebuild the client and try once more.
                self.log_exception(
                    exception=exp,
                    message=(
                        "Office365 client session was closed unexpectedly during subscription activation; "
                        "rebuilding client."
                    ),
                )
                self._reset_client()
                await self._activate_subscriptions(False)
        except (FailedToListO365Subscriptions, FailedToActivateO365Subscription) as exp:
            if isinstance(exp, FailedToActivateSomeO365Subscriptions):
                self._active_content_types = set(exp.active_content_types)

            if not self._active_content_types:
                raise

            # an activation interrupted by the shutdown is not a failure
            if self.running:
                self._schedule_activation_retry(exp)
        else:
            self._active_content_types = set(active_content_types)
            self._activation_pending = False
            self._activation_failures = 0
            self.log(
                message=f"Office365 subscriptions are active for {', '.join(sorted(active_content_types))}",
                level="info",
            )

    def _schedule_activation_retry(self, error: O365Exception) -> None:
        """Log a partial activation failure with an actionable message, and schedule the next attempt"""
        self._activation_pending = True
        self._activation_failures += 1
        delay = backoff_delay(self._activation_failures)
        self._next_activation_attempt = time.monotonic() + delay

        if isinstance(error, FailedToActivateSomeO365Subscriptions):
            summary = f"Failed to activate the Office365 subscriptions for {', '.join(sorted(error.failures))}"
        elif isinstance(error, FailedToListO365Subscriptions):
            summary = "Failed to list the Office365 subscriptions"
        else:
            summary = "Failed to activate the Office365 subscriptions"

        active_types = ", ".join(sorted(self._active_content_types))
        self.log_exception(exception=error, message=f"{summary}.")
        self.log(
            message=(
                f"{summary}. Events from {active_types} are still collected. {error.hint} "
                f"Next attempt in {delay} seconds."
            ),
            level="error",
        )

    async def _retry_pending_activation(self) -> None:
        """Retry the activation of the failed subscriptions, once their backoff delay has elapsed"""
        if self._activation_pending and time.monotonic() >= self._next_activation_attempt:
            await self._activate_subscriptions(True)

    async def activate_subscriptions(self):
        """Activates an Office 365 subscriptions"""
        await self._activate_subscriptions(True)

    def _refresh_active_content_types(self, content_types: list[str]) -> bool:
        """Update the active subscriptions from Microsoft, as they can be disabled while the connector is running.

        Schedules the reactivation of the missing subscriptions, and returns whether any subscription is active.
        """
        self._active_content_types = set(content_types)

        missing_types = EXPECTED_SUBSCRIPTIONS - self._active_content_types
        if missing_types and not self._activation_pending:
            self._activation_pending = True
            self._next_activation_attempt = 0.0  # at the next cycle
            self.log(
                message=(
                    f"The Office365 subscriptions for {', '.join(sorted(missing_types))} are no longer active: "
                    "they will be reactivated."
                ),
                level="warning",
            )

        return bool(self._active_content_types)

    async def forward_next_batches(self, checkpoint: Checkpoint):
        # Don't advance the checkpoint when no subscription is active anymore: the reactivation is scheduled instead
        content_types = await self.client.list_subscriptions()
        if not self._refresh_active_content_types(content_types):
            return

        start_pull_date = checkpoint.offset
        end_pull_date = datetime.now(UTC)

        for start_date, end_date in split_date_range(
            start_pull_date, end_pull_date, timedelta(minutes=self.time_range_interval)
        ):
            intermediate_start_time = time.time()

            # Get events for the current date range
            async for list_of_events in self.pull_content(start_date, end_date, content_types):
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
                await self._retry_pending_activation()

                # Don't advance the checkpoint while no subscription is active: the events would be skipped
                if self._active_content_types:
                    await self.forward_next_batches(checkpoint)
                # get the ending time and compute the duration to forward the events
                end_time = time.time()
                batch_duration = end_time - start_time
                # compute the remaining sleeping time. If greater than 0, sleep
                delta_sleep = self._frequency - batch_duration
                if delta_sleep > 0:
                    await asyncio.sleep(delta_sleep)
            except SessionClosedError as exp:
                if not self.running:
                    self.log(
                        message="Stopping event forwarding: client session closed during shutdown.",
                        level="info",
                    )
                    return
                self.log_exception(
                    message="Office365 client session was closed unexpectedly; rebuilding client and continuing.",
                    exception=exp,
                )
                self._reset_client()
                if self.running:
                    await asyncio.sleep(self._frequency)
            except Exception as error:
                if not self.running:
                    self.log(message="Stopping event forwarding: the connector is stopping.", level="info")
                    return

                # Restart the connector, so the SDK stops it if the error persists (see `run`), when:
                # - the error needs an action from the customer: it won't disappear by retrying
                # - no subscription is active: no event can be collected until the activation succeeds
                if isinstance(error, O365Exception) and (error.is_actionable or not self._active_content_types):
                    raise

                self.log_exception(error, message="Failed to forward events")
                # Continue the loop to retry after logging
                await asyncio.sleep(self._frequency)

    def _handle_stop_signal(self, loop):
        """
        Handle graceful shutdown
        """
        self.log(message="Received stop signal", level="info")
        loop.create_task(self.shutdown())

    async def collect_events(self):
        """
        Fetch and forward the events
        """
        # Get the current asyncio loop
        loop = asyncio.get_running_loop()

        # Register shutdown handler
        loop.add_signal_handler(signal.SIGTERM, self._handle_stop_signal, loop)
        loop.add_signal_handler(signal.SIGINT, self._handle_stop_signal, loop)

        # Initialize the checkpoint
        checkpoint = Checkpoint(self.data_path, self.configuration.intake_key)

        # Activate the subscriptions from scratch, as the connector can be restarted after an error
        self._active_content_types = set()
        self._activation_pending = True
        self._activation_failures = 0

        try:
            await self.activate_subscriptions()
            await self.forward_events_forever(checkpoint)
        finally:
            # Ensure client is closed on exit (cached_property stores in __dict__)
            if "client" in self.__dict__ and not getattr(self, "_client_closed", False):
                await self.client.close()
                self._client_closed = True

    def run(self) -> None:
        """Main execution thread

        Runs the async event collection loop. The connector will continuously pull events
        from Office 365 Management API and forward them to Sekoia intake until stopped.

        An error that prevents any collection (no active subscription, authentication or permission error)
        is raised to the SDK after a backoff delay: the SDK restarts the connector and, if the error persists,
        stops it with a critical log.
        """
        self.log(message="Office365 Trigger has started", level="info")

        try:
            asyncio.run(self.collect_events())

        except SessionClosedError as session_error:
            if self.running:
                self.log_exception(
                    session_error,
                    message="Office365 client session closed unexpectedly; the connector will stop.",
                )
            else:
                self.log(
                    message="Office365 client session closed during shutdown.",
                    level="info",
                )

        except Exception as error:
            if not self.running:
                self.log(message=f"Office365 connector stopped while handling an error: {error}", level="info")
                return

            self._wait_before_restart(error)
            if self.running:
                raise

        self.log(message="Office365 Trigger has stopped", level="info")

    def _wait_before_restart(self, error: Exception) -> None:
        """Log an actionable message, then wait before letting the SDK restart the connector.

        The SDK restarts the connector immediately and counts the consecutive errors (reset when events are sent):
        the backoff avoids hammering Microsoft until the SDK stops the connector.
        """
        delay = backoff_delay(self._error_count + 1)
        hint = error.hint if isinstance(error, O365Exception) else GENERIC_HINT
        self.log(
            message=(
                f"The Office365 connector can't collect events ({type(error).__name__}: {error}). "
                f"{hint} The connector will restart in {delay} seconds."
            ),
            level="error",
        )
        self._stop_event.wait(delay)
