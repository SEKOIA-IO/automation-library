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
    def latest_alert_id(self) -> int:
        """
        Get the latest alert id from the previous run if present.

        Returns:
            int | None:
        """
        with self.context as cache:
            result: int | None = cache.get("latest_alert_id_from_previous_run")

        return result or 0

    @property
    def latest_start_event_date(self) -> datetime:
        """
        Get the latest start event date from the previous run if present otherwise we get the date from 1 day ago.

        Returns:
            datetime:
        """
        now = datetime.now(timezone.utc)

        with self.context as cache:
            most_recent_date_seen_str = cache.get("latest_start_event_date_from_previous_run")

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

    def forward_next_batches(self) -> None:
        """
        Successively queries the Lacework Central API while more are available
        and the current batch is not too big.
        """
        start_alerts_date = self.latest_start_event_date
        start_alerts_id = self.latest_alert_id

        alerts, next_page_url = self.client.get_alerts_by_date(start_alerts_date)

        data_to_push = []
        current_lag: int = 0
        if alerts:
            # As we want to save latest alert id as well we need to get the latest alert id from the current batch
            latest_alerts_id = max([item["alertId"] for item in alerts])
            if latest_alerts_id < start_alerts_id:
                latest_alerts_id = start_alerts_id

            latest_alerts_date = max([LaceworkApiClient.parse_response_time(item["startTime"]) for item in alerts])

            data_to_push.extend([alert for alert in alerts if alert["alertId"] > start_alerts_id])

            while next_page_url:
                alerts, next_page_url = self.client.get_alerts_by_page(next_page_url)
                if alerts:
                    latest_alerts_id_next_page = max([item["alertId"] for item in alerts])
                    if latest_alerts_id_next_page > latest_alerts_id:
                        latest_alerts_id = latest_alerts_id_next_page

                    data_to_push.extend([alert for alert in alerts if alert["alertId"] > start_alerts_id])

                    last_date_page_date = max(
                        [LaceworkApiClient.parse_response_time(item["startTime"]) for item in alerts]
                    )

                    if last_date_page_date > latest_alerts_date:
                        latest_alerts_date = last_date_page_date

                    if len(data_to_push) > self.configuration.chunk_size:
                        self.log(message=f"Sending a batch of {len(data_to_push)} messages", level="info")
                        OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(data_to_push))
                        self.push_events_to_intakes(
                            events=[orjson.dumps(item).decode("utf-8") for item in data_to_push]
                        )
                        current_lag = int(time.time() - latest_alerts_date.timestamp())
                        data_to_push = []

            if len(data_to_push) > 0:
                self.log(message=f"Sending a batch of {len(data_to_push)} messages", level="info")
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(data_to_push))
                self.push_events_to_intakes(events=[orjson.dumps(item).decode("utf-8") for item in data_to_push])
                current_lag = int(time.time() - latest_alerts_date.timestamp())

            with self.context as cache:
                cache["latest_start_event_date_from_previous_run"] = latest_alerts_date.isoformat()
                cache["latest_alert_id_from_previous_run"] = latest_alerts_id

        # Monitor the events lag
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)
