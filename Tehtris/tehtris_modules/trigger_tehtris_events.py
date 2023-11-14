import time
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from functools import cached_property

import orjson
from dateutil.parser import isoparse
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from tehtris_modules import TehtrisModule
from tehtris_modules.client import ApiClient
from tehtris_modules.constants import EVENTS_ENDPOINT
from tehtris_modules.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class TehtrisEventConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    filter_id: int | str | None = None
    chunk_size: int = 10000


class TehtrisEventConnector(Connector):
    """
    This connector fetches events from Tehtris API
    """

    module: TehtrisModule
    configuration: TehtrisEventConnectorConfiguration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.from_date = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.fetch_events_limit = 100

    @cached_property
    def client(self):
        return ApiClient(self.module.configuration.apikey)

    def __fetch_next_events(self, from_date: datetime, offset: int):
        # We don't retrieve messages older than one hour
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        if from_date < one_hour_ago:
            from_date = one_hour_ago

        params = {
            "fromDate": int(from_date.timestamp()),
            "limit": self.fetch_events_limit,
            "offset": offset,
        }

        if self.configuration.filter_id is not None:
            params["filterID"] = self.configuration.filter_id

        headers = {"Accept": "application/json"}
        url = f"{self.module.configuration.base_url}/{EVENTS_ENDPOINT}"
        response = self.client.get(url, params=params, headers=headers)

        if not response.ok:
            # Exit trigger if we can't authenticate against the server
            level = "critical" if response.status_code in [401, 403] else "error"
            self.log(
                message=(
                    f"Request on Tehtris API to fetch events of tenant {self.module.configuration.tenant_id}"
                    f"failed with status {response.status_code} - {response.reason}"
                ),
                level=level,
                response=response.text
            )
            return []
        else:
            events = response.json()
            self.log(
                message=(
                    f"Got {len(events)} events from Tehtris API for tenant {self.module.configuration.tenant_id}"
                    f"with status {response.status_code}"
                ),
                level="debug",
            )
            return events

    def fetch_events(self) -> Generator[list, None, None]:
        has_more_message = True
        most_recent_date_seen = self.from_date
        offset = 0

        while has_more_message:
            # fetch events from the current context
            next_events = self.__fetch_next_events(self.from_date, offset)
            INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(next_events))

            # if the number of fetched events equals the limit, additional events are remaining
            has_more_message = len(next_events) == self.fetch_events_limit

            # increase the offset (to iter over pages)
            offset = offset + len(next_events)

            if next_events:
                # get the greater date seen in this list of events
                events_date = list(
                    sorted(
                        filter(
                            lambda x: x is not None,
                            map(lambda x: x["time"], next_events),
                        )
                    )
                )
                last_event_date = isoparse(events_date[-1])

                # save the greater date ever seen
                if last_event_date > most_recent_date_seen:
                    most_recent_date_seen = last_event_date

                # forward current events
                yield next_events

        # save the most recent date
        if most_recent_date_seen > self.from_date:
            self.from_date = most_recent_date_seen

        now = datetime.now(timezone.utc)
        current_lag = now - most_recent_date_seen
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).observe(int(current_lag.total_seconds()))

    def next_batch(self):
        # save the starting time
        batch_start_time = time.time()

        # Fetch next batch
        batch_of_events = []
        for events in self.fetch_events():
            # for each fetched event
            for event in events:
                # add to the batch as json-serialized object
                batch_of_events.append(orjson.dumps(event).decode("utf-8"))

                # if the batch is full, push it
                if len(batch_of_events) >= self.configuration.chunk_size:
                    self.log(
                        message=f"Forward {len(batch_of_events)} events to the intake",
                        level="info",
                    )
                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))
                    self.push_events_to_intakes(events=batch_of_events)
                    batch_of_events = []

        # if the last batch is not empty, push it
        if len(batch_of_events) > 0:
            self.log(
                message=f"Forward {len(batch_of_events)} events to the intake",
                level="info",
            )
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))
            self.push_events_to_intakes(events=batch_of_events)

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(
            message=f"Fetch and forward {len(batch_of_events)} events in {batch_duration} seconds",
            level="info",
        )
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(
                message=f"Next batch in the future. Waiting {delta_sleep} seconds",
                level="info",
            )
            time.sleep(delta_sleep)

    def run(self):
        while True:
            self.next_batch()
