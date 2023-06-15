import os
import time
from functools import cached_property

import orjson
from requests.exceptions import HTTPError
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.metrics import PrometheusExporterThread, make_exporter
from sekoia_automation.storage import PersistentJSON

from sophos_module.base import SophosConnector
from sophos_module.client import SophosApiClient
from sophos_module.client.auth import SophosApiAuthentication
from sophos_module.helper import normalize_message
from sophos_module.metrics import FORWARD_EVENTS_DURATION, INCOMING_EVENTS, OUTCOMING_EVENTS


class SophosEDRConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    exclude_types: list[str] | None = None


class SophosEDREventsTrigger(SophosConnector):
    """
    The Sophos EDR trigger reads the next batch of messages exposed by the Sophos Central
    APIs and forward it to the playbook run.

    Quick notes
    - Authentication on API is OAuth2 and access token expiration is handled.
    - A margin of 300sec is added to the expiration date of oauth2 token.

    """

    configuration: SophosEDRConfiguration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self._exporter = None

    @property
    def cursor(self) -> str | None:
        with self.context as cache:
            return cache.get("cursor")

    @cursor.setter
    def cursor(self, cursor: str):
        with self.context as cache:
            cache["cursor"] = cursor

    @cached_property
    def pagination_limit(self):
        return max(self.configuration.chunk_size, 1000)

    @cached_property
    def client(self):
        auth = SophosApiAuthentication(
            api_host=self.module.configuration.api_host,
            authorization_url=self.module.configuration.oauth2_authorization_url,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
        )
        return SophosApiClient(auth=auth)

    def start_monitoring(self):
        super().start_monitoring()
        # start the prometheus exporter
        self._exporter = make_exporter(
            PrometheusExporterThread, int(os.environ.get("WORKER_PROM_LISTEN_PORT", "8010"), 10)
        )
        self._exporter.start()

    def stop_monitoring(self):
        super().stop_monitoring()
        if self._exporter:
            self._exporter.stop()

    def run(self):
        self.log(message="Sophos Events Trigger has started", level="info")

        try:
            while self.running:
                try:
                    start = time.time()

                    self.forward_next_batches()

                    # compute the duration of the last events fetching
                    duration = int(time.time() - start)
                    FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(duration)

                    # Compute the remaining sleeping time
                    delta_sleep = self.configuration.frequency - duration
                    # if greater than 0, sleep
                    if delta_sleep > 0:
                        time.sleep(delta_sleep)

                except HTTPError as ex:
                    self.log_exception(ex, message="Failed to get next batch of events")
                except Exception as ex:
                    self.log_exception(ex, message="An unknown exception occurred")
                    raise
        finally:
            self.log(message="Sophos Events Trigger has stopped", level="info")

    def get_next_events(self, cursor: str | None) -> dict | None:
        # set parameters
        parameters = {
            "limit": self.pagination_limit,
        }

        # if defined, set the cursor
        if cursor:
            parameters["cursor"] = cursor
        # otherwise, get events starting from the last 5 minutes
        else:
            parameters["from_date"] = int(time.time()) - 300

        # if defined, exclude some type of events from the response
        exclude_types = self.configuration.exclude_types
        if exclude_types and len(exclude_types) > 0:
            parameters["exclude_types"] = exclude_types

        # Get the events
        response = self.client.list_siem_events(parameters=parameters)

        # Something failed
        if not response.ok:
            self.log(
                message=(
                    "Request on Sophos Central API to fetch events of failed with"
                    f" status {response.status_code} - {response.reason}"
                ),
                level="error",
            )

            return None

        return response.json()

    def forward_next_batches(self) -> None:
        """
        Successively queries the Sophos Central API while more are available
        and the current batch is not too big.
        """
        has_more_messages = True
        cursor = self.cursor

        messages = []
        while has_more_messages and self.running:
            has_more_messages = False

            batch = self.get_next_events(cursor)
            if batch is None:
                break

            if has_more := batch.get("has_more", False):
                has_more_messages = has_more

            if (next_cursor := batch.get("next_cursor")) is not None:
                cursor = next_cursor

            items = batch.get("items", [])
            INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(items))
            for message in items:
                normalized_message = normalize_message(message)
                messages.append(orjson.dumps(normalized_message).decode("utf-8"))

            if len(messages) > self.pagination_limit:
                self.log(message=f"Sending a batch of {len(messages)} messages", level="info")
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(messages))
                self.push_events_to_intakes(events=messages)
                messages = []

        self.cursor = cursor

        if messages:
            self.log(message=f"Sending a batch of {len(messages)} messages", level="info")
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(messages))
            self.push_events_to_intakes(events=messages)
        else:
            self.log(message="No messages to forward", level="info")
