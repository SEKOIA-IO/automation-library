import datetime
import time
from functools import cached_property

from datetime import datetime, timedelta, timezone
from typing import Any

import orjson
from requests.exceptions import HTTPError
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON
from urllib3.exceptions import HTTPError as BaseHTTPError

import sys

sys.path.append("../")
from lacework_module.base import LaceworkModule
from lacework_module.client import LaceworkApiClient
from lacework_module.client.auth import LaceworkAuthentication
from lacework_module.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_EVENTS, OUTCOMING_EVENTS


class LaceworkConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    exclude_types: list[str] | None = None
    chunk_size: int = 1000


class LaceworkEventsTrigger(Connector):
    """
    The Lacework trigger reads the next batch of messages and forward it to the playbook run.

    Quick notes
    - Authentication on API is OAuth2 and access token expiration is handled.
    - A margin of 300sec is added to the expiration date of oauth2 token.

    """

    module: LaceworkModule
    configuration: LaceworkConfiguration

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.from_date = ""
        self.context = PersistentJSON("context.json", "./")

    @cached_property
    def pagination_limit(self) -> Any:
        return max(self.configuration.chunk_size, 1000)

    @cached_property
    def client(self) -> LaceworkApiClient:
        auth = LaceworkAuthentication(
            lacework_url=self.module.configuration.lacework_url,
            access_key=self.module.configuration.access_key,
            secret_key=self.module.configuration.secret_key,
        )
        return LaceworkApiClient(base_url=self.module.configuration.lacework_url, auth=auth)

    @property
    def most_recent_date_seen(self):
        now = datetime.now(timezone.utc)

        with self.context as cache:
            most_recent_date_seen_str = cache.get("most_recent_date_seen")

            # if undefined, retrieve events from the last day
            if most_recent_date_seen_str is None:
                before_one_day = now - timedelta(days=1)
                return before_one_day.strftime("%Y-%m-%dT%H:%M:%SZ")

            # parse the most recent date seen
            most_recent_date_seen = datetime.strptime(most_recent_date_seen_str, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )

            # We don't retrieve messages older than almost 6 months
            one_month_ago = now - timedelta(days=30)
            if most_recent_date_seen < one_month_ago:
                most_recent_date_seen = one_month_ago

            return most_recent_date_seen.strftime("%Y-%m-%dT%H:%M:%SZ")

    @most_recent_date_seen.setter
    def most_recent_date_seen(self, recent_date):
        add_one_seconde = datetime.strptime(recent_date, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=timezone.utc
        ) + timedelta(seconds=1)
        self.from_date = add_one_seconde.strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.context as cache:
            cache["most_recent_date_seen"] = self.from_date

    def run(self) -> None:
        self.log(message="Lacework Events Trigger has started", level="info")

        try:
            while self.running:
                start = time.time()

                try:
                    self.forward_next_batches()
                except (HTTPError, BaseHTTPError) as ex:
                    self.log_exception(ex, message="Failed to get next batch of events")
                except Exception as ex:
                    self.log_exception(ex, message="An unknown exception occurred")
                    raise

                # compute the duration of the last events fetching
                duration = int(time.time() - start)
                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(duration)

                # Compute the remaining sleeping time
                delta_sleep = self.configuration.frequency - duration
                # if greater than 0, sleep
                if delta_sleep > 0:
                    time.sleep(delta_sleep)
        finally:
            self.log(message="Lacework Events Trigger has stopped", level="info")

    def get_next_events(self, url: str | None) -> Any | None:
        # if defined, set the next page url
        if url:
            response = self.client.get(url=url)

        # otherwise, display the first page of alerts
        else:
            response = self.client.list_alerts()

        # Something failed
        if not response.ok:
            self.log(
                message=(
                    "Request on Lacework Central API to fetch events of failed with"
                    f" status {response.status_code} - {response.reason}"
                ),
                level="error",
            )

            return None

        return response.json()

    def _get_most_recent_timestamp_from_items(self, items: list[dict[Any, Any]]) -> float:
        def _extract_timestamp(item: dict[Any, Any]) -> float:
            RFC3339_STRICT_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
            return datetime.strptime(item["startTime"], RFC3339_STRICT_FORMAT).timestamp()

        later = 0.0
        for item in items:
            if _extract_timestamp(item) > later:
                later = _extract_timestamp(item)
        return later

    def forward_next_batches(self) -> None:
        """
        Successively queries the Lacework Central API while more are available
        and the current batch is not too big.
        """
        has_more_messages = True
        nextPage = None
        messages = []
        while has_more_messages and self.running:
            has_more_messages = False
            batch = self.get_next_events(nextPage)
            if batch is None:
                break

            if batch.get("content", {}).get("paging", {}).get("urls", {}).get("nextPage") != None:
                has_more_messages = True
                nextPage = batch.get("content", {}).get("paging", {}).get("urls", {}).get("nextPage")

            items = batch.get("data", [])
            if len(items) > 0:
                self.most_recent_date_seen = str(
                    datetime.fromtimestamp(self._get_most_recent_timestamp_from_items(items)).strftime(
                        "%Y-%m-%dT%H:%M:%S.%fZ"
                    )
                )
                events_lag = int(
                    time.time() - datetime.strptime(self.most_recent_date_seen, "%Y-%m-%dT%H:%M:%SZ").timestamp()
                )
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(events_lag)
                INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(items))

            for message in items:
                messages.append(orjson.dumps(message).decode("utf-8"))

            if len(messages) > self.pagination_limit:
                self.log(message=f"Sending a batch of {len(messages)} messages", level="info")
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(messages))
                self.push_events_to_intakes(events=messages)
                messages = []

        if messages:
            print(messages)
            self.log(message=f"Sending a batch of {len(messages)} messages", level="info")
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(messages))
            self.push_events_to_intakes(events=messages)
        else:
            self.log(message="No messages to forward", level="info")
