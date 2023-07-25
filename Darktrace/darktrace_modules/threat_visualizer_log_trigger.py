import time
import traceback
from functools import cached_property
from urllib.parse import urljoin

import orjson
import requests
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from darktrace_modules import DarktraceModule
from darktrace_modules.client import ApiClient
from darktrace_modules.logging import get_logger

logger = get_logger()


class ThreatVisualizerLogConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 1
    ratelimit_per_minute: int = 30
    filter: str | None = None
    q: str | None = None


class ThreatVisualizerLogConnector(Connector):
    """
    This connector fetches threat visualizer logs from the Darktrace API
    """

    module: DarktraceModule
    configuration: ThreatVisualizerLogConnectorConfiguration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

    @property
    def last_ts(self) -> int:
        with self.context as cache:
            ts = cache.get("last_ts")
            if ts is None:
                # Set starttime one hour in the past.
                ts = round((time.time() - 3600) * 1000)
                self.last_ts = ts
            return ts

    @last_ts.setter
    def last_ts(self, last_ts: str):
        with self.context as cache:
            cache["last_ts"] = last_ts

    def stop(self, _, __):
        self.log(message="Stopping Darktrace threat visualizer logs connector", level="info")
        # Exit signal received, asking the processor to stop
        super().stop()

    @cached_property
    def client(self):
        return ApiClient(
            self.module.configuration.public_key,
            self.module.configuration.private_key,
            ratelimit_per_minute=self.configuration.ratelimit_per_minute,
        )

    def request_events(self) -> requests.models.Response:
        params = {"starttime": str(self.last_ts), "includeallpinned": "false"}
        url = urljoin(self.module.configuration.api_url, "modelbreaches")

        response = self.client.get(url, params=params)
        return response

    def refine_response(self, response: list) -> list:
        # as we use the time variable of the newest event to set last_ts, this event has to be removed in the next batch of events.
        if response != [] and response[0]["time"] == self.last_ts:
            return response[1:]
        return response

    def next_batch(self):
        logger.debug(f"New batch")
        # save the start time
        batch_start_time = time.time()
        response = []
        try:
            response = self.request_events().json()
            logger.debug(f"Response from API: {response}")
        except ValueError:
            self.log(
                message="The server response is not a json: " + str(response),
                level="warn",
            )
            return
        if type(response) is list:
            response = self.refine_response(response)
            # if the response is not empty, push it
            if response != []:
                batch_of_events = [orjson.dumps(event).decode("utf-8") for event in response]
                self.push_events_to_intakes(events=batch_of_events)
                self.last_ts = response[-1]["time"]
                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )
            else:
                self.log(
                    message="No events to forward",
                    level="info",
                )
        else:
            self.log(
                message="Response is not a list : " + str(response),
                level="warn",
            )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        logger.debug(f"Batch was handled in {batch_duration} seconds")

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            logger.debug(f"Next batch in the future. Waiting {delta_sleep} seconds")
            time.sleep(delta_sleep)

    def run(self):
        self.log(message="Start fetching Darktrace threat visualizer logs", level="info")

        while self.running:
            try:
                self.next_batch()
            except Exception as error:
                traceback.print_exc()
                self.log_exception(error, message="Failed to forward events")
