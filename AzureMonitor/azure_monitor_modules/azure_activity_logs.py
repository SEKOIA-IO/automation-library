import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Any, Generator

import dateutil.parser
import orjson
from azure.identity import ClientSecretCredential
from azure.mgmt.monitor import MonitorManagementClient
from cachetools import Cache, LRUCache
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import AzureMonitorModule
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


class AzureActivityLogsConnectorConfiguration(DefaultConnectorConfiguration):
    subscription_id: str
    filter_resource: str | None = None
    filter_resource_group: str | None = None
    filter_resource_provider: str | None = None
    filter_correlation_id: str | None = None
    frequency: int = 60
    chunk_size: int = 1000


class AzureActivityLogsConnector(Connector):
    module: AzureMonitorModule
    configuration: AzureActivityLogsConnectorConfiguration

    def __init__(self, *args: Any, **kwargs: Any | None) -> None:
        super().__init__(*args, **kwargs)

        self.context = PersistentJSON("context.json", self._data_path)
        self.cursor = CheckpointDatetime(
            path=self._data_path, start_at=timedelta(hours=1), ignore_older_than=timedelta(days=90)
        )
        self.from_date = self.cursor.offset

        # This cache should be big enough to cover all events within 1 second.
        self.cache_size = 1000
        self.events_cache: Cache[str, bool] = self.load_events_cache()

    def load_events_cache(self) -> Cache[str, bool]:
        result: LRUCache[str, bool] = LRUCache(maxsize=self.cache_size)

        with self.cursor._context as cache:
            events_ids = cache.get("events_cache", [])

        for event_id in events_ids:
            result[event_id] = True

        return result

    def save_events_cache(self) -> None:
        with self.cursor._context as cache:
            cache["events_cache"] = list(self.events_cache.keys())

    def filter_processed_events(self, events: list[dict[str, Any]]) -> Generator[dict[str, Any], None, None]:
        for event in events:
            event_id = event["id"]
            if event_id in self.events_cache:
                continue

            self.events_cache[event_id] = True
            yield event

    @cached_property
    def client(self) -> "MonitorManagementClient":
        return MonitorManagementClient(
            credential=ClientSecretCredential(
                client_id=self.module.configuration.client_id,
                client_secret=self.module.configuration.client_secret,
                tenant_id=self.module.configuration.tenant_id,
            ),
            subscription_id=self.configuration.subscription_id,
        )

    def fetch_events(self) -> Generator[list[Any], None, None]:
        most_recent_date_seen: datetime = self.from_date

        dt = most_recent_date_seen.isoformat().replace("+00:00", "Z")
        ft = f"eventTimestamp ge '{dt}'"

        # Expecting only one of these
        if self.configuration.filter_resource:
            ft = f"eventTimestamp ge '{dt}' and resourceUri eq '{self.configuration.filter_resource}'"

        elif self.configuration.filter_resource_group:
            ft = f"eventTimestamp ge '{dt}' and resourceGroupName eq '{self.configuration.filter_resource_group}'"

        elif self.configuration.filter_resource_provider:
            ft = f"eventTimestamp ge '{dt}' and resourceProvider eq '{self.configuration.filter_resource_provider}'"

        elif self.configuration.filter_correlation_id:
            ft = f"eventTimestamp ge '{dt}' and correlationId eq '{self.configuration.filter_correlation_id}'"

        # Using batches to avoid storing all events from all pages in the memory
        batch = []

        for event_data in self.client.activity_logs.list(filter=ft):
            # Serialize using the internal serializer to preserve original field names
            event = event_data.serialize(keep_readonly=True)
            batch.append(event)

            timestamp = dateutil.parser.parse(event["eventTimestamp"])
            if timestamp > most_recent_date_seen:
                most_recent_date_seen = timestamp

            if len(batch) >= self.configuration.chunk_size:
                yield batch
                batch = []

        if len(batch) > 0:
            yield batch

        if most_recent_date_seen > self.from_date:
            self.from_date = most_recent_date_seen
            self.cursor.offset = most_recent_date_seen

        now = datetime.now(timezone.utc)
        current_lag = now - most_recent_date_seen
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(int(current_lag.total_seconds()))

    def next_batch(self) -> None:
        # save the starting time
        batch_start_time = time.time()

        for events in self.fetch_events():
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in self.filter_processed_events(events)]

            # if the batch is full, push it
            if len(batch_of_events) > 0:
                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))
                self.push_events_to_intakes(events=batch_of_events)
                self.save_events_cache()

            else:
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)
                self.log(
                    message="No events to forward",
                    level="info",
                )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(f"Fetched and forwarded events in {batch_duration} seconds", level="info")
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(f"Next batch in the future. Waiting {delta_sleep} seconds", level="info")
            time.sleep(delta_sleep)

    def check_filters_configuration(self) -> None:
        # Check if more than 1 filter defined
        filters = [
            self.configuration.filter_resource_group,
            self.configuration.filter_resource,
            self.configuration.filter_resource_provider,
            self.configuration.filter_correlation_id,
        ]
        num_filters_used = sum(map(bool, filters))
        if num_filters_used > 1:
            self.log(message="More than one filter use. Please set only one filter", level="critical")
            raise ValueError

    def run(self) -> None:
        self.log(message="Start fetching Azure Activity Logs", level="info")
        self.check_filters_configuration()

        while self.running:
            try:
                self.next_batch()

            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
