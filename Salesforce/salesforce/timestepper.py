"""Timestepper for orchestrating event collection with configurable time windows."""

import datetime
import time
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

    def ranges(
        self,
    ) -> Generator[tuple[datetime.datetime, datetime.datetime], None, None]:
        """
        Yield time windows for event collection.

        Continuously yields (start, end) tuples, sleeping when approaching real-time.

        Yields:
            Tuple of (start, end) datetimes for each time window
        """
        while True:
            # Return the current time range
            yield self.start, self.end

            # Compute the next time range
            next_end = self.end + self.frequency
            now = datetime.datetime.now(datetime.timezone.utc) - self.timedelta

            # Compute current lag
            current_lag = now - next_end
            self.connector.log(
                message=f"Current lag {int(current_lag.total_seconds())} seconds.",
                level="info",
            )
            EVENTS_LAG.labels(intake_key=self.connector.configuration.intake_key).set(int(current_lag.total_seconds()))

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
                time.sleep(max_difference)

            self.start = self.end
            self.end = next_end

    @classmethod
    def create(
        cls,
        connector: AsyncConnector,
        frequency: int = 600,
        timedelta: int = 15,
        start_time: int = 6,
    ) -> "TimeStepper":
        """
        Create a new TimeStepper for initial run.

        Args:
            connector: The connector instance
            frequency: Time window step in seconds (default: 600 = 10 minutes)
            timedelta: Event lag buffer in minutes (default: 15)
            start_time: Hours ago to start collecting (default: 6), 0 means start from now

        Returns:
            New TimeStepper instance
        """
        t_frequency = datetime.timedelta(seconds=frequency)
        t_timedelta = datetime.timedelta(minutes=timedelta)

        if start_time == 0:
            end = datetime.datetime.now(datetime.timezone.utc) - t_timedelta
        else:
            end = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=start_time)

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
