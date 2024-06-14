import json
import time
from datetime import UTC, datetime, timedelta
from functools import cached_property
from pathlib import Path
from time import sleep

from prometheus_client import Counter, Histogram
from sekoia_automation.connector import Connector
from sekoia_automation.storage import get_data_path

from office365.metrics import FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS

from .checkpoint import Checkpoint
from .configuration import Office365Configuration
from .errors import FailedToActivateO365Subscription
from .helpers import split_date_range
from .office365_client import Office365API


class Office365Connector(Connector):
    configuration: Office365Configuration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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

    def pull_content(self, start_date: datetime, end_date: datetime) -> list[str]:
        """Pulls content from Office 365 subscriptions

        Args:
            start_date (datetime): Start date of the interval
            end_date (datetime): End date of the interval

        Returns:
            list[dict]: List of events recevied for the interval
        """
        pulled_events: list[str] = []

        content_types = self.client.list_subscriptions()
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
        OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(events))

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

    def forward_next_batches(self, checkpoint: Checkpoint):
        start_time = time.time()
        start_pull_date = checkpoint.offset
        end_pull_date = datetime.now(UTC)

        for start_date, end_date in split_date_range(start_pull_date, end_pull_date, timedelta(minutes=30)):
            events = self.pull_content(start_date, end_date)
            self.forward_events(events)

        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(time.time() - start_time)

        checkpoint.offset = end_pull_date
        sleep(60)

    def run(self):
        """Main execution thread

        It starts by creating and launching the clear_cache subthread
        Activate subscriptions
        Then loop every 60 seconds, pull events using the Office 365 API and forward them.
        When stopped, the clear_cache is stopped and joined as well so that we wait for it to end gracefully.
        """
        self.activate_subscriptions()
        checkpoint = Checkpoint(self._data_path, self.configuration.intake_key)

        while self.running:
            self.forward_next_batches(checkpoint)

        self._executor.shutdown(wait=True)
