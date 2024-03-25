import time
from functools import cached_property

from datetime import datetime, timedelta, timezone
from typing import Any
from dateutil.parser import isoparse

import orjson
from requests.exceptions import HTTPError
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON
from urllib3.exceptions import HTTPError as BaseHTTPError
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
        self.context = PersistentJSON("context.json", self._data_path)

    @property
    def most_recent_date_seen(self) -> datetime:
        now = datetime.now(timezone.utc)

        with self.context as cache:
            most_recent_date_seen_str = cache.get("most_recent_date_seen")

            if most_recent_date_seen_str == None:
                return now - timedelta(days=1)

            most_recent_date_seen = isoparse(most_recent_date_seen_str)

            one_week_ago = now - timedelta(days=7)
            if most_recent_date_seen.replace(tzinfo=timezone.utc) < one_week_ago:
                most_recent_date_seen = one_week_ago

            return most_recent_date_seen

    @most_recent_date_seen.setter
    def most_recent_date_seen(self, recent_date: datetime) -> None:
        # save the greatest date
        if self.from_date == "" or isoparse(self.from_date) < recent_date:
            self.from_date = str(recent_date)
        with self.context as cache:
            cache["most_recent_date_seen"] = self.from_date

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
        except ValueError as ex:
            self.log_exception(ex, message=("No more messages to forward"))
            return None

    def get_response_by_timestamp(self) -> Any | None:
        response = self.client.get_alerts_from_date(self.most_recent_date_seen.strftime("%Y-%m-%dT%H:%M:%SZ"))
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
            return response.json()
        except ValueError as ex:
            self.log(
                message=("No more messages to forward"),
                level="info",
            )
            return None

    def _get_most_recent_timestamp_from_items(self, items: list[dict[Any, Any]]) -> float:
        def _extract_timestamp(item: dict[Any, Any]) -> float:
            RFC3339_STRICT_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
            return datetime.strptime(item["endTime"], RFC3339_STRICT_FORMAT).replace(tzinfo=timezone.utc).timestamp()

        later = 0.0
        for item in items:
            if _extract_timestamp(item) > later:
                later = _extract_timestamp(item)
        return float(later)

    def forward_next_batches(self) -> None:
        """
        Successively queries the Lacework Central API while more are available
        and the current batch is not too big.
        """
        first_batch = self.get_response_by_timestamp()
        if first_batch and first_batch != "":
            next_page_url = first_batch.get("content", {}).get("paging", {}).get("urls", {}).get("nextPage")
            items = first_batch.get("data", [])
            last_date = self._get_most_recent_timestamp_from_items(items)
            events_lag = int(time.time() - last_date)
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(events_lag)
            self.most_recent_date_seen = datetime.utcfromtimestamp(last_date)
            messages = [orjson.dumps(message).decode("utf-8") for message in items]
            self.log(message=f"Sending the first batch of {len(messages)} messages", level="info")
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(messages))
            self.push_events_to_intakes(events=messages)
            grouped_data = []
            while next_page_url:
                response_next_page = self.get_next_events(next_page_url)
                if response_next_page:
                    next_page_url = (
                        response_next_page.get("content", {}).get("paging", {}).get("urls", {}).get("nextPage")
                    )
                    next_page_items = response_next_page.get("items", [])
                    next_page_items = [orjson.dumps(message).decode("utf-8") for message in next_page_items]
                    grouped_data.extend(next_page_items)
                    last_date = self._get_most_recent_timestamp_from_items(next_page_items)
                    events_lag = int(time.time() - last_date)
                    EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(events_lag)
                    self.most_recent_date_seen = datetime.utcfromtimestamp(last_date)

                    if len(grouped_data) > self.pagination_limit:
                        self.log(message=f"Sending a batch of {len(grouped_data)} messages", level="info")
                        OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(grouped_data))
                        self.push_events_to_intakes(events=grouped_data)
                        grouped_data = []

            if grouped_data != []:
                self.log(message=f"Sending a batch of {len(grouped_data)} messages", level="info")
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(grouped_data))
                self.push_events_to_intakes(events=grouped_data)

        else:
            self.log(message="No messages to forward", level="info")
