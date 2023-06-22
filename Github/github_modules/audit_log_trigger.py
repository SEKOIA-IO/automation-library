import time
import traceback
from functools import cached_property

import orjson
import requests
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from github_modules import GithubModule
from github_modules.client import ApiClient
from github_modules.logging import get_logger

logger = get_logger()


class AuditLogConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 1
    timebuffer: int = 60000
    ratelimit_per_minute: int = 83
    filter: str | None = None
    q: str | None = None


class AuditLogConnector(Connector):
    """
    This connector fetches audit logs from the Github API
    """

    module: GithubModule
    configuration: AuditLogConnectorConfiguration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

    @property
    def last_ts(self) -> int:
        with self.context as cache:
            ts = cache.get("last_ts")
            if ts is None:
                ts = round(time.time() * 1000) - (self.configuration.timebuffer)
                self.last_ts = ts
            return ts

    @last_ts.setter
    def last_ts(self, last_ts: str):
        with self.context as cache:
            cache["last_ts"] = last_ts

    def stop(self, _, __):
        self.log(message="Stopping Github audit logs connector", level="info")
        # Exit signal received, asking the processor to stop
        super().stop()

    @cached_property
    def client(self):
        return ApiClient(
            self.module.configuration.apikey, ratelimit_per_minute=self.configuration.ratelimit_per_minute
        )

    def request_events(self) -> requests.models.Response:
        api_url = "https://api.github.com/orgs/" + self.module.configuration.org_name + "/audit-log"
        params = {"phrase": "created:>" + str(self.last_ts), "order": "asc"}

        response = self.client.get(api_url, params=params)
        return response

    def _refine_batch(self, batch, batch_start_time) -> list:
        # Remove events that are in the time buffer
        for index, event in enumerate(batch):
            if event["@timestamp"] > int((batch_start_time * 1000) - self.configuration.timebuffer):
                return batch[0:index]
        return batch

    def next_batch(self):
        # save the starting time
        batch_start_time = time.time()
        response = self.request_events().json()

        if type(response) is list:
            response = self._refine_batch(response, batch_start_time)

            # if the response is not empty, push it
            if response != []:
                self.last_ts = response[-1]["@timestamp"]
                batch_of_events = [orjson.dumps(event).decode("utf-8") for event in response]
                self.push_events_to_intakes(events=batch_of_events)
                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )
            else:
                self.log(
                    message="No events to forward ",
                    level="info",
                )
        else:
            self.log(
                message=str(response),
                level="warn",
            )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        logger.debug(f"Fetched and forwarded events in {batch_duration} seconds")

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            logger.debug(f"Next batch in the future. Waiting {delta_sleep} seconds")
            time.sleep(delta_sleep)

    def run(self):
        self.log(message="Start fetching Github audit logs", level="info")

        while self.running:
            try:
                self.next_batch()
            except Exception as error:
                traceback.print_exc()
                self.log_exception(error, message="Failed to forward events")
