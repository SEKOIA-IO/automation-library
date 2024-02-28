import json
import time
from datetime import UTC, datetime, timedelta
from functools import cached_property
from pathlib import Path
from time import sleep

from prometheus_client import Counter, Histogram
from sekoia_automation.connector import Connector
from sekoia_automation.storage import get_data_path

from .configuration import Office365Configuration
from .errors import FailedToActivateO365Subscription
from .office365_client import Office365API

# Declare prometheus metrics
prom_namespace = "office365_intakes"

OUTGOING_EVENTS = Counter(
    name="forwarded_events",
    documentation="Number of events forwarded to SEKOIA.IO",
    namespace=prom_namespace,
    labelnames=["datasource", "intake_key"],
)

FORWARD_EVENTS_DURATION = Histogram(
    name="forward_events_duration",
    documentation="Duration to collect and forward events",
    namespace=prom_namespace,
    labelnames=["datasource", "intake_key"],
)


class Office365Connector(Connector):
    configuration: Office365Configuration

    @cached_property
    def _last_pull_date(self) -> Path:
        return get_data_path().joinpath(f"o365_{self.configuration.intake_key}_last_pull")

    @property
    def last_pull_date(self) -> datetime:
        """Reads the last events pull date from S3

        Office 365 can return events from up to 7 days ago. If the last pull date is older than that, or if no
        last pull date is found, we return a "7 days ago" date instead. If the stored date is timezone-naive or not
        in UTC, we raise an error to avoid the risk of confusions => all dates must be timezone-aware,
        this is an arbitrary choice to avoid any inconsistencies.

        Raises:
            ValueError: If the date found on S3 was stored as timezone-naive or not in UTC

        Returns:
            datetime: Last pull date
        """
        try:
            last_pull_date = datetime.fromisoformat(self._last_pull_date.read_text())
        except FileNotFoundError:
            return datetime.now(UTC) - timedelta(days=7)
        if last_pull_date.tzinfo != UTC:
            raise ValueError(f"Last pull date timezone should be {UTC} but is {last_pull_date.tzinfo} instead")
        elif not last_pull_date or datetime.now(UTC) - last_pull_date > timedelta(days=7):
            return datetime.now(UTC) - timedelta(days=7)
        else:
            return last_pull_date

    @last_pull_date.setter
    def last_pull_date(self, new_last_pull_date: datetime):
        """Stores the last events pull date on S3

        We expect stored date to be always timezone-aware and in UTC

        Args:
            new_last_pull_date (datetime): Date to be stored

        Raises:
            ValueError: If the user tries to store a timezone-naive date or not in UTC
        """
        if new_last_pull_date.tzinfo != UTC:
            raise ValueError(f"Last pull date timezone should be {UTC} but is {new_last_pull_date.tzinfo} instead")
        self._last_pull_date.write_text(new_last_pull_date.isoformat())

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

    def _split_date_range(
        self, start_date: datetime, end_date: datetime, delta: timedelta
    ) -> list[tuple[datetime, datetime]]:
        """Splits a date range in shorter intervals with a set max duration

        This is a recursive method that, given a start and end date, will create a first tuple for the first 30
        minutes of the interval, then call itself to create the tuples of the subsequent 30 minutes intervals and
        append them at the end of the list of intervals.
        The last interval of the list may be of less than 30 minutes if the global interval duration is not a multiple
        of 30 minutes.

        Args:
            start_date (datetime): Current start date of the to-be-split interval
            end_date (datetime): End date of the to-be-split interval
            delta (timedelta): Max duration of the splits

        Returns:
            list[tuple[datetime, datetime]]: A list of subintervals covering of all the global interval
        """
        if end_date - start_date <= delta:
            return [(start_date, end_date)]
        else:
            return [(start_date, start_date + delta)] + self._split_date_range(start_date + delta, end_date, delta)

    def pull_content(self, start_pull_date: datetime, end_pull_date: datetime) -> list[str]:
        """Pulls content from Office 365 subscriptions

        Args:
            start_pull_date (datetime): Start date of the pull interval
            end_pull_date (datetime): End date of the pull interval

        Returns:
            list[dict]: List of events recevied for the pull interval
        """
        pulled_events: list[str] = []

        content_types = self.client.list_subscriptions()
        for start_date, end_date in self._split_date_range(start_pull_date, end_pull_date, timedelta(minutes=30)):
            for content_type in content_types:
                # Get the paginated contents from a subscription
                for contents in self.client.get_subscription_contents(
                    content_type, start_time=start_date, end_time=end_date
                ):
                    for content in contents:
                        events = self.client.get_content(content["contentUri"])
                        for event in events:
                            pulled_events.append(json.dumps(event))

        return pulled_events

    def forward_events(self, events: list[str]):
        """Sends event to Sekoia intake

        Args:
            events (list[dict]): Events to forward to intake
        """
        self.log(f"Pushing {len(events)} event(s) to intake", level="info")
        OUTGOING_EVENTS.labels(intake_key=self.configuration.intake_key, datasource="office365").inc(len(events))

        self.push_events_to_intakes(events)

    def activate_subscriptions(self):
        """Activates an Office 365 subscriptions"""
        try:
            self.client.activate_subscriptions()
        except FailedToActivateO365Subscription as exp:
            self.log_exception(
                exception=exp,
                message="An exception occurred when trying to subscribe to Office365 events.",
            )

    def run(self):
        """Main execution thread

        It starts by creating and launching the clear_cache subthread
        Activate subscriptions
        Then loop every 60 seconds, pull events using the Office 365 API and forward them.
        When stopped, the clear_cache is stopped and joined as well so that we wait for it to end gracefully.
        """
        self.activate_subscriptions()

        while self.running:
            start_time = time.time()
            start_pull_date = self.last_pull_date
            end_pull_date = datetime.now(UTC)

            events = self.pull_content(start_pull_date, end_pull_date)
            self.forward_events(events)

            FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key, datasource="office365").observe(
                time.time() - start_time
            )

            self.last_pull_date = end_pull_date
            sleep(60)

        self._executor.shutdown(wait=True)
