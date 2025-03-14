import json
from datetime import UTC, datetime, timedelta
from functools import cached_property
from threading import Event, Lock, Thread
from time import sleep, time
from pathlib import Path

from cachetools import Cache, LRUCache
from management.mgmtsdk_v2.entities.activity import Activity
from management.mgmtsdk_v2.entities.threat import Threat
from management.mgmtsdk_v2.exceptions import UnauthorizedException
from management.mgmtsdk_v2.services.activity import ActivitiesFilter
from management.mgmtsdk_v2.services.threat import ThreatQueryFilter
from management.mgmtsdk_v2_1.mgmt import Management
from sekoia_automation.connector import Connector
from sekoia_automation.checkpoint import CheckpointDatetime

from sentinelone_module.base import SentinelOneModule
from sentinelone_module.helpers import filter_collected_events
from sentinelone_module.logging import get_logger
from sentinelone_module.logs.configuration import SentinelOneLogsConnectorConfiguration
from sentinelone_module.logs.helpers import get_latest_event_timestamp
from sentinelone_module.logs.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS

logger = get_logger()


class SentinelOneLogsConsumer(Thread):
    """
    Each endpoint of SentinelOne logs API is consumed in its own separate thread.
    """

    def __init__(self, connector: "SentinelOneLogsConnector", consumer_type: str):
        super().__init__()

        self.log = connector.log
        self.log_exception = connector.log_exception
        self.configuration = connector.configuration
        self.connector = connector
        self.module = connector.module
        self.consumer_type = consumer_type
        self._stop_event = Event()

        self.cursor = CheckpointDatetime(
            path=self.connector.data_path,
            start_at=timedelta(days=1),
            ignore_older_than=timedelta(days=1),
            lock=self.connector.context_lock,
        )
        self.from_date = self.cursor.offset
        self.session_events_cache: Cache = self.load_events_cache()

    def stop(self):
        """Sets the stop event for the thread"""
        self._stop_event.set()

    @property
    def running(self) -> bool:
        """Returns if the thread's stop event is NOT set

        Returns:
            bool: True if thread is running (stop event not set)
        """
        return not self._stop_event.is_set()

    @cached_property
    def management_client(self):
        """Connects to SentinelOne using the client

        Returns:
            Management: SentinelOne client instance
        """
        return Management(hostname=self.module.configuration.hostname, api_token=self.module.configuration.api_token)

    def load_events_cache(self) -> Cache:
        events_cache: LRUCache = LRUCache(maxsize=1000)

        with self.cursor._context as ctx:
            for cached_id in ctx.get("events_cache", []):
                events_cache[cached_id] = True

        return events_cache

    def save_events_cache(self, sessions: Cache) -> None:
        with self.cursor._context as cache:
            cache["events_cache"] = list(sessions.keys())

    @staticmethod
    def _serialize_events(events: list[Activity] | list[Threat] | list[dict]) -> list:
        """Serializes a list of events by generating a dict and converting it to JSON

        Args:
            events (list[Activity] | list[Threat] | list[dict]): List of events to serialize

        Returns:
            list: List of json dumped as strings
        """
        serialized_events = []
        for event in events:
            event_dict = event if isinstance(event, dict) else event.__dict__
            non_empty_json = {k: v for (k, v) in event_dict.items() if v is not None}
            non_empty_json_str = json.dumps(non_empty_json)
            serialized_events.append(non_empty_json_str)
        return serialized_events

    def pull_events(self, last_timestamp: datetime | None) -> list:
        raise NotImplementedError

    def next_batch(self) -> None:
        # save the starting time
        batch_start_time = time()
        batch_duration: int = 0

        try:
            # get the batch
            events_id = self.pull_events(self.from_date)

            # get the ending time and compute the duration to fetch the events
            batch_end_time = time()
            batch_duration = int(batch_end_time - batch_start_time)
            logger.debug(f"Fetched and forwarded events", duration=batch_duration, nb_events=len(events_id))
            FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

            # log the number of forwarded events
            log_message = "No events to forward"
            if len(events_id) > 0:
                log_message = f"Fetched and forwarded {len(events_id)} events"

            self.log(message=log_message, level="info")
        except Exception as ex:
            self.log_exception(ex, message="Failed to forward events")

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            logger.debug(f"Next batch in the future. Pause the connector", pause=delta_sleep)
            sleep(delta_sleep)

    def run(self):
        """Main loop for the connector

        It pulls alerts and threats every 60s and stores retrieval duration in Prometheus
        """
        # Validate settings
        try:
            self.management_client.system.get_info()
        except UnauthorizedException as unauthorized_exception:
            self.log(f"Connector is unauthorized to retrieve system info", level="warning")
            raise unauthorized_exception

        while self.running:
            self.next_batch()

        # save sessions cache to the context
        self.save_events_cache(self.session_events_cache)

        self.connector._executor.shutdown(wait=True)


class SentinelOneActivityLogsConsumer(SentinelOneLogsConsumer):
    def __init__(self, connector: "SentinelOneLogsConnector"):
        super().__init__(connector, "activity")

    def pull_events(self, last_timestamp: datetime | None) -> list:
        """Fetches activities from SentinelOne"""
        # Set  filters
        query_filter = ActivitiesFilter()
        query_filter.apply(key="limit", val=1000)
        query_filter.apply(key="sortBy", val="createdAt")
        query_filter.apply(key="sortOrder", val="asc")

        if last_timestamp:
            query_filter.apply(key="createdAt", val=last_timestamp.isoformat(), op="gt")

        events_id = []
        while self.running:
            # Fetch activities
            activities = self.management_client.activities.get(query_filter)
            nb_activities = len(activities.data)
            logger.debug("Collected activities", nb=nb_activities)

            INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(nb_activities)

            # discard already collected events
            selected_events = filter_collected_events(
                activities.data, lambda activity: activity.id, self.session_events_cache
            )

            # Push events
            if len(selected_events) > 0:
                events_id.extend(self.connector.push_events_to_intakes(self._serialize_events(selected_events)))

            # Send Prometheus metrics
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(selected_events))

            # Update context with latest event date
            current_lag: int = 0
            latest_event_timestamp = get_latest_event_timestamp(selected_events)
            if latest_event_timestamp is not None:
                self.cursor.offset = latest_event_timestamp
                self.from_date = latest_event_timestamp
                current_lag = int((datetime.now(UTC) - latest_event_timestamp).total_seconds())

            EVENTS_LAG.labels(intake_key=self.configuration.intake_key, type="activities").set(current_lag)

            if activities.pagination["nextCursor"] is None:
                break

            query_filter.apply(key="cursor", val=activities.pagination["nextCursor"])

        return events_id


class SentinelOneThreatLogsConsumer(SentinelOneLogsConsumer):
    def __init__(self, connector: "SentinelOneLogsConnector"):
        super().__init__(connector, "threat")

    def pull_events(self, last_timestamp: datetime | None):
        """Fetches threats from SentinelOne"""
        query_filter = ThreatQueryFilter()
        query_filter.apply(key="limit", val=1000)
        query_filter.apply(key="sortBy", val="createdAt")
        query_filter.apply(key="sortOrder", val="asc")

        if last_timestamp:
            query_filter.apply(key="createdAt", val=last_timestamp.isoformat(), op="gt")

        events_id = []
        while self.running:
            # Fetch threats
            threats = self.management_client.client.get(endpoint="threats", params=query_filter.filters)
            nb_threats = len(threats.data)
            logger.debug("Collected nb_threats", nb=nb_threats)

            # discard already collected events
            selected_events = filter_collected_events(
                threats.data, lambda threat: threat["id"], self.session_events_cache
            )

            # Push events
            if len(selected_events) > 0:
                events_id.extend(self.connector.push_events_to_intakes(self._serialize_events(selected_events)))

            # Send Prometheus metrics
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(selected_events))

            # Update context with the latest event date
            current_lag: int = 0
            latest_event_timestamp = get_latest_event_timestamp(selected_events)
            if latest_event_timestamp is not None:
                self.cursor.offset = latest_event_timestamp
                self.from_date = latest_event_timestamp
                current_lag = int((datetime.now(UTC) - latest_event_timestamp).total_seconds())

            EVENTS_LAG.labels(intake_key=self.configuration.intake_key, type="threats").set(current_lag)

            if threats.pagination["nextCursor"] is None:
                break

            query_filter.apply(key="cursor", val=threats.pagination["nextCursor"])

        return events_id


CONSUMER_TYPES = {"activity": SentinelOneActivityLogsConsumer, "threat": SentinelOneThreatLogsConsumer}


class SentinelOneLogsConnector(Connector):
    module: SentinelOneModule
    configuration: SentinelOneLogsConnectorConfiguration

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.context_lock = Lock()

    @property
    def data_path(self) -> Path:
        path_to_data: Path = self._data_path
        return path_to_data

    def start_consumers(self) -> dict:
        """Starts children threads for each supported type

        Returns:
            dict: Children threads and their type
        """
        consumers = {}

        for consumer_type, consumer_class in CONSUMER_TYPES.items():
            consumer = consumer_class(connector=self)
            consumer.start()
            consumers[consumer_type] = consumer

        return consumers

    def supervise_consumers(self, consumers: dict):
        """Restarts children threads if needed

        Args:
            consumers (dict): Children threads and their type
        """
        for consumer_type, consumer in consumers.items():
            if consumer is None or (not consumer.is_alive() and consumer.running):
                self.log(message=f"Restarting {consumer_type} consumer", level="info")
                consumers[consumer_type] = CONSUMER_TYPES[consumer_type](connector=self)
                consumers[consumer_type].start()

    def stop_consumers(self, consumers: dict):
        """Stops children threads

        Args:
            consumers (dict): Children threads and their type
        """
        for consumer_type, consumer in consumers.items():
            if consumer is not None and consumer.is_alive():
                self.log(message=f"Stopping {consumer_type} consumer", level="info")
                consumer.stop()

    def run(self):
        """Main loop for SentinelOne connector that starts children threads"""
        consumers = self.start_consumers()

        while self.running:
            self.supervise_consumers(consumers)
            sleep(5)

        self.stop_consumers(consumers)
