"""Timestepper for orchestrating event collection with configurable time windows."""

import datetime
from collections.abc import Generator

from sekoia_automation.aio.connector import AsyncConnector

from .metrics import EVENTS_LAG


class TimeStepper:
    """
    Generator-based time window manager for iterative event collection.

    Handles time range stepping with intelligent sleep logic when approaching real-time.
    """

    def __init__(
        self,
        connector: AsyncConnector,
        start: datetime.datetime,
        end: datetime.datetime,
        frequency: datetime.timedelta,
        timedelta: datetime.timedelta,
    ):
        """
        Initialize TimeStepper.

        Args:
            connector: The connector instance for logging and configuration
            start: Start datetime of current window
            end: End datetime of current window
            frequency: Step size - how much to advance per iteration
            timedelta: Timeshift/lag - how far in the past to collect
        """
        self.connector = connector
        self.start = start
        self.end = end
        self.frequency = frequency
        self.timedelta = timedelta
        self.sleep_duration: float = 0.0

    def ranges(
        self,
    ) -> Generator[tuple[datetime.datetime, datetime.datetime], None, None]:
        """
        Yield time windows for event collection.

        Continuously yields (start, end) tuples, setting sleep_duration when approaching real-time.
        The connector is responsible for sleeping based on sleep_duration.

        Yields:
            Tuple of (start, end) datetimes for each time window
        """
        while True:
            # Return the current time range
            yield self.start, self.end

            # Reset sleep duration for this iteration's computation
            self.sleep_duration = 0.0

            # Compute the next time range
            next_end = self.end + self.frequency
            now = datetime.datetime.now(datetime.timezone.utc) - self.timedelta

            # Compute current lag
            current_lag = now - next_end
            lag_seconds = int(current_lag.total_seconds())
            if lag_seconds >= 0:
                self.connector.log(
                    message=f"Current lag: {lag_seconds} seconds behind real-time.",
                    level="info",
                )

                EVENTS_LAG.labels(intake_key=self.connector.configuration.intake_key).set(lag_seconds)
            else:
                self.connector.log(
                    message=f"Caught up: {abs(lag_seconds)} seconds ahead of real-time window.",
                    level="info",
                )

                EVENTS_LAG.labels(intake_key=self.connector.configuration.intake_key).set(0)

            # If the next end is in the future
            if next_end > now:
                # Compute the max date allowed in the future and set the next_end accordingly
                current_difference = int((next_end - now).total_seconds())
                max_difference = min(current_difference, self.frequency.total_seconds())
                next_end = now + datetime.timedelta(seconds=max_difference)

                self.connector.log(
                    message=f"Timerange in the future. Waiting {max_difference} seconds for next batch.",
                    level="info",
                )
                self.sleep_duration = max_difference

            self.start = self.end
            self.end = next_end

    @classmethod
    def create(
        cls,
        connector: AsyncConnector,
        frequency: int = 600,
        timedelta: int = 15,
        initial_hours_ago: int = 6,
    ) -> "TimeStepper":
        """
        Create a new TimeStepper for initial run.

        Args:
            connector: The connector instance
            frequency: Time window step in seconds (default: 600 = 10 minutes)
            timedelta: Event lag buffer in minutes (default: 15)
            initial_hours_ago: Hours ago to start collecting (default: 6), 0 means start from now

        Returns:
            New TimeStepper instance
        """
        t_frequency = datetime.timedelta(seconds=frequency)
        t_timedelta = datetime.timedelta(minutes=timedelta)

        if initial_hours_ago == 0:
            end = datetime.datetime.now(datetime.timezone.utc) - t_timedelta
        else:
            end = (
                datetime.datetime.now(datetime.timezone.utc)
                - datetime.timedelta(hours=initial_hours_ago)
                - t_timedelta
            )

        start = end - t_frequency

        return cls(connector, start, end, t_frequency, t_timedelta)

    @classmethod
    def create_from_time(
        cls,
        connector: AsyncConnector,
        start: datetime.datetime,
        frequency: int = 600,
        timedelta: int = 15,
    ) -> "TimeStepper":
        """
        Create a TimeStepper from a specific start time (for recovery from cache).

        Args:
            connector: The connector instance
            start: Start datetime to resume from
            frequency: Time window step in seconds (default: 600)
            timedelta: Event lag buffer in minutes (default: 15)

        Returns:
            New TimeStepper instance
        """
        t_frequency = datetime.timedelta(seconds=frequency)
        t_timedelta = datetime.timedelta(minutes=timedelta)

        end = start + t_frequency

        return cls(connector, start, end, t_frequency, t_timedelta)
