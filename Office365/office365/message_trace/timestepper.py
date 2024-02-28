import datetime
import time
from collections.abc import Generator

from sekoia_automation.trigger import Trigger

from .metrics import EVENTS_LAG


class TimeStepper:
    def __init__(
        self,
        trigger: Trigger,
        start: datetime.datetime,
        end: datetime.datetime,
        frequency: datetime.timedelta,
        timedelta: datetime.timedelta,
    ):
        self.trigger = trigger
        self.start = start
        self.end = end
        self.frequency = frequency
        self.timedelta = timedelta

    def ranges(
        self,
    ) -> Generator[tuple[datetime.datetime, datetime.datetime], None, None]:
        while True:
            # return the current time range
            yield (self.start, self.end)

            # compute the next time range
            next_end = self.end + self.frequency
            now = datetime.datetime.now(datetime.UTC) - self.timedelta

            # Compute current lag
            current_lag = now - next_end
            self.trigger.log(
                message=f"Current lag {int(current_lag.total_seconds())} seconds.",
                level="info",
            )
            EVENTS_LAG.labels(intake_key=self.trigger.configuration.intake_key).set(int(current_lag.total_seconds()))

            # If the next end is in the future
            if next_end > now:
                # compute the max date allowed in the future and set the next_end according
                current_difference = int((next_end - now).total_seconds())
                max_difference = min(
                    current_difference, self.frequency.total_seconds()
                )  # limit the end date in the future
                next_end = now + datetime.timedelta(seconds=max_difference)

                self.trigger.log(
                    message=f"Timerange in the future. Waiting {max_difference} seconds for next batch.",
                    level="info",
                )
                time.sleep(max_difference)

            self.start = self.end
            self.end = next_end

    @classmethod
    def create(
        cls,
        trigger: Trigger,
        frequency: int = 60,
        timedelta: int = 1,
        start_time: int = 1,
    ) -> "TimeStepper":
        t_frequency = datetime.timedelta(seconds=frequency)
        t_timedelta = datetime.timedelta(minutes=timedelta)

        if start_time == 0:
            end = datetime.datetime.now(datetime.UTC) - t_timedelta
        else:
            end = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=start_time)

        start = end - t_frequency

        return cls(trigger, start, end, t_frequency, t_timedelta)

    @classmethod
    def create_from_time(
        cls,
        trigger: Trigger,
        start: datetime.datetime,
        frequency: int = 60,
        timedelta: int = 1,
    ) -> "TimeStepper":
        t_frequency = datetime.timedelta(seconds=frequency)
        t_timedelta = datetime.timedelta(minutes=timedelta)

        end = start + t_frequency

        return cls(trigger, start, end, t_frequency, t_timedelta)
