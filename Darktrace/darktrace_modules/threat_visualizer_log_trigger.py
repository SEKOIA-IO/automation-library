import time
import traceback
from functools import cached_property
from threading import Event, Thread
from urllib.parse import urljoin

import orjson
import requests
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from darktrace_modules import DarktraceModule, Endpoints
from darktrace_modules.client import ApiClient
from darktrace_modules.logging import get_logger
from darktrace_modules.metrics import (
    EVENTS_LAG,
    FORWARD_EVENTS_DURATION,
    INCOMING_MESSAGES,
    OUTCOMING_EVENTS,
)

logger = get_logger()


class ThreatVisualizerLogConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 1
    ratelimit_per_minute: int = 30
    filter: str | None = None
    q: str | None = None
    verify_certificate: bool = True


class ThreatVisualizerLogConsumer(Thread):
    def __init__(self, connector: "ThreatVisualizerLogConnector", endpoint: Endpoints):
        super().__init__()

        self.connector = connector
        self.endpoint = endpoint

        self._stop_event = Event()

        context_name = self.endpoint.value.replace("/", "_") + "_context.json"
        self.context = PersistentJSON(context_name, connector._data_path)

        if self.endpoint == Endpoints.MODEL_BREACHES:
            self.time_field = "time"
        elif self.endpoint == Endpoints.AI_ANALYST:
            self.time_field = "createdAt"

    def stop(self):
        self._stop_event.set()

    @property
    def running(self):
        return not self._stop_event.is_set()

    @property
    def last_ts(self) -> int:
        with self.context as cache:
            ts = cache.get("last_ts")
            if ts is None:
                ts = round(time.time() * 1000)
                self.last_ts = ts
            return ts

    @last_ts.setter
    def last_ts(self, last_ts: str):
        with self.context as cache:
            cache["last_ts"] = last_ts

    @cached_property
    def client(self):
        return ApiClient(
            self.connector.module.configuration.public_key,
            self.connector.module.configuration.private_key,
            ratelimit_per_minute=self.connector.configuration.ratelimit_per_minute,
        )

    def request_events(self) -> requests.models.Response:
        params = {"starttime": str(self.last_ts), "includeallpinned": "false"}
        url = urljoin(self.connector.module.configuration.api_url, self.endpoint.value)
        # save cert in file to pass to request
        response = self.client.get(url, params=params, verify=self.connector.configuration.verify_certificate)
        return response

    def refine_response(self, response: list) -> list:
        # as we use the time variable of the newest event to set last_ts,
        # this event has to be removed in the next batch of events.
        if response != [] and response[0][self.time_field] == self.last_ts:
            return response[1:]
        return response

    def next_batch(self):
        logger.debug(f"New batch")
        # save the start time
        batch_start_time = time.time()
        response = []
        try:
            response = self.request_events()
            response = response.json()
            logger.debug(f"Response from API: {response}")
            INCOMING_MESSAGES.labels(intake_key=self.connector.configuration.intake_key).inc(len(response))
        except ValueError:  # pragma: no cover
            self.connector.log(
                message="The server response is not a json: " + str(response),
                level="warning",
            )
            return

        if type(response) is list:
            response = self.refine_response(response)
            # if the response is not empty, push it
            if response != []:
                for event in response:
                    event["log_type"] = self.endpoint.value
                batch_of_events = [orjson.dumps(event).decode("utf-8") for event in response]

                OUTCOMING_EVENTS.labels(intake_key=self.connector.configuration.intake_key).inc(len(batch_of_events))
                self.connector.push_events_to_intakes(events=batch_of_events)
                for event in batch_of_events:
                    print("\n", event, "\n")
                self.last_ts = response[-1][self.time_field]
                self.connector.log(
                    message=f"Forwarded {len(batch_of_events)} {self.endpoint.name} events to the intake",
                    level="info",
                )

                # compute the lag
                now = time.time()
                current_lag = now - self.last_ts / 1000
                EVENTS_LAG.labels(intake_key=self.connector.configuration.intake_key).observe(int(current_lag))
            else:  # pragma: no cover
                self.connector.log(
                    message="No events to forward",
                    level="info",
                )
        else:  # pragma: no cover
            self.connector.log(
                message="Response is not a list : " + str(response),
                level="warning",
            )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        logger.debug(f"Fetched and forwarded events in {batch_duration} seconds")
        FORWARD_EVENTS_DURATION.labels(intake_key=self.connector.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.connector.configuration.frequency - batch_duration
        if delta_sleep > 0:  # pragma: no cover
            logger.debug(f"Next batch in the future. Waiting {delta_sleep} seconds")
            time.sleep(delta_sleep)

    def run(self):
        self.connector.log(
            message=f"Start fetching Darktrace threat visualizer {self.endpoint.name} logs",
            level="info",
        )  # pragma: no cover

        while self.running:
            try:
                self.next_batch()
            except Exception as error:  # pragma: no cover
                traceback.print_exc()
                self.connector.log_exception(error, message="Failed to forward events")


class ThreatVisualizerLogConnector(Connector):
    """
    This connector fetches threat visualizer logs from the Darktrace API
    It uses threading for each darktrace endpoint
    """

    module: DarktraceModule
    configuration: ThreatVisualizerLogConnectorConfiguration

    def start_consumers(self):
        consumers = {}
        for endpoint in Endpoints:
            self.log(message=f"Start {endpoint.name} consumer", level="info")  # pragma: no cover

            consumers[endpoint] = ThreatVisualizerLogConsumer(connector=self, endpoint=endpoint)
            consumers[endpoint].start()

        return consumers

    def supervise_consumers(self, consumers):
        """Check consumer list and restart consumer if not alive."""
        for endpoint, consumer in consumers.items():
            if consumer is None or (not consumer.is_alive() and consumer.running):
                self.log(message=f"Restarting {endpoint.name} consumer", level="info")  # pragma: no cover

                consumers[endpoint] = ThreatVisualizerLogConsumer(connector=self, endpoint=endpoint)
                consumers[endpoint].start()

    def stop_consumers(self, consumers):
        for endpoint, consumer in consumers.items():
            if consumer is not None and consumer.is_alive():
                self.log(message=f"Stopping {endpoint.name} consumer", level="info")  # pragma: no cover
                consumer.stop()

    def run(self):
        self.log(message="Start fetching Darktrace threat visualizer logs", level="info")  # pragma: no cover

        consumers = self.start_consumers()
        while self.running:
            self.supervise_consumers(consumers)
            time.sleep(5)

        self.stop_consumers(consumers)

    def stop(self, _, __):
        self.log(message="Stopping Darktrace threat visualizer logs connector", level="info")  # pragma: no cover
        # Exit signal received, asking the processor to stop
        super().stop()
