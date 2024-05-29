import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Any

import orjson
from dateutil.parser import isoparse
from requests.exceptions import HTTPError
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON
from urllib3.exceptions import HTTPError as BaseHTTPError

from lacework_module.base import LaceworkModule
from lacework_module.client import LaceworkApiClient
from lacework_module.client.auth import LaceworkAuthentication
from lacework_module.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


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
        self.context = PersistentJSON("context.json", self._data_path)

    @property
    def most_recent_date_seen(self) -> datetime:
        now = datetime.now(timezone.utc)

        with self.context as cache:
            most_recent_date_seen_str = cache.get("most_recent_date_seen")

            if most_recent_date_seen_str is None:
                return now - timedelta(days=1)

            most_recent_date_seen = isoparse(most_recent_date_seen_str)

            one_week_ago = now - timedelta(days=7)
            if most_recent_date_seen.replace(tzinfo=timezone.utc) < one_week_ago:
                most_recent_date_seen = one_week_ago

            return most_recent_date_seen

    @cached_property
    def client(self) -> LaceworkApiClient:
        auth = LaceworkAuthentication(
            lacework_url=self.module.configuration.account,
            access_key=self.module.configuration.key_id,
            secret_key=self.module.configuration.secret,
        )

        return LaceworkApiClient(
            base_url=self.module.configuration.account,
            auth=auth,
            nb_retries=5,
            ratelimit_per_hour=480,
        )

    def run(self) -> None:  # pragma: no cover
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

    def get_next_events(self, url: str) -> Any | None:
        response = self.client.get(url=url)
        if not response.ok:
            self.log(
                message=(
                    "Request on Lacework Central API to fetch next page events failed with"
                    f" status {response.status_code} - {response.reason}"
                ),
                level="error",
            )

            return None
        try:
            return response.json()
        except ValueError:
            self.log(
                message="No more messages to forward",
                level="info",
            )
            return None

    def get_response_by_timestamp(self, date: datetime) -> dict[str, Any] | None:
        response = self.client.get_alerts_from_date(date.strftime("%Y-%m-%dT%H:%M:%SZ"))
        if not response.ok:
            self.log(
                message=(
                    "Request on Lacework Central API to fetch events failed with"
                    f" status {response.status_code} - {response.reason}"
                ),
                level="error",
            )

            return None

        try:
            result: dict[str, Any] = response.json()

            return result
        except ValueError:
            self.log(message="No more messages to forward", level="info")

            return None

    def forward_next_batches(self) -> None:
        """
        Successively queries the Lacework Central API while more are available
        and the current batch is not too big.
        """
        start_events_date = self.most_recent_date_seen
        first_batch = self.get_response_by_timestamp(start_events_date)
        if first_batch is not None:
            next_page_url = LaceworkApiClient.get_next_page_url(first_batch)
            first_batch_events = first_batch.get("data", [])

            last_date = max([LaceworkApiClient.parse_event_time(item["endTime"]) for item in first_batch_events])

            self.log(message=f"Sending the first batch of {len(first_batch_events)} messages", level="info")
            self.push_events_to_intakes(
                events=[orjson.dumps(message).decode("utf-8") for message in first_batch_events])
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(first_batch_events))

            grouped_data = []
            while next_page_url:
                response_next_page = self.get_next_events(next_page_url)
                if response_next_page:
                    next_page_url = LaceworkApiClient.get_next_page_url(response_next_page)
                    next_page_items = response_next_page.get("data", [])

                    grouped_data.extend([orjson.dumps(message).decode("utf-8") for message in next_page_items])
                    last_date_page_date = max(
                        [LaceworkApiClient.parse_event_time(item["endTime"]) for item in next_page_items]
                    )

                    if last_date_page_date > last_date:
                        last_date = last_date_page_date

                    if len(grouped_data) > self.configuration.chunk_size:
                        self.log(message=f"Sending a batch of {len(grouped_data)} messages", level="info")
                        OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(grouped_data))
                        self.push_events_to_intakes(events=grouped_data)
                        grouped_data = []

            if len(grouped_data) > 0:
                self.log(message=f"Sending a batch of {len(grouped_data)} messages", level="info")
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(grouped_data))
                self.push_events_to_intakes(events=grouped_data)

            if start_events_date < last_date:
                with self.context as cache:
                    cache["most_recent_date_seen"] = last_date.isoformat()

            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(int(time.time() - last_date.timestamp()))
