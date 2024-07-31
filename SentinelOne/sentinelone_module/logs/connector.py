import json
from datetime import UTC, datetime, timedelta
from functools import cached_property
from logging import getLogger
from threading import Event, Thread
from time import sleep, time

from dateutil.parser import isoparse
from management.mgmtsdk_v2.entities.activity import Activity
from management.mgmtsdk_v2.entities.threat import Threat
from management.mgmtsdk_v2.exceptions import UnauthorizedException
from management.mgmtsdk_v2.services.activity import ActivitiesFilter
from management.mgmtsdk_v2.services.threat import ThreatQueryFilter
from management.mgmtsdk_v2_1.mgmt import Management
from sekoia_automation.connector import Connector
from sekoia_automation.storage import PersistentJSON

from sentinelone_module.base import SentinelOneModule
from sentinelone_module.logs.configuration import SentinelOneLogsConnectorConfiguration
from sentinelone_module.logs.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS, INCOMING_MESSAGES

# Declare prometheus metrics
prom_namespace = "symphony_module_common"

logger = getLogger()


class SentinelOneLogsConsumer(Thread):
    """
    Each endpoint of SentinelOne logs API is consumed in its own separate thread.
    """

    def __init__(self, connector: "SentinelOneLogsConnector"):
        super().__init__()

        self.context = PersistentJSON("context.json", connector._data_path)
        self.log = connector.log
        self.configuration = connector.configuration
        self.connector = connector
        self.module = connector.module

        self._stop_event = Event()

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

    @property
    def _cache_last_event_date(self) -> datetime:
        """
        Get last event date.

        Returns:
            datetime:
        """
        now = datetime.now(UTC)
        one_day_ago = (now - timedelta(days=1)).replace(microsecond=0)

        with self.context as cache:
            last_event_date_str = cache.get("last_event_date")

        # If undefined, retrieve events from the last 1 hour
        if last_event_date_str is None:
            return one_day_ago

        # Parse the most recent date seen
        last_event_date = isoparse(last_event_date_str).replace(microsecond=0)

        # We don't retrieve messages older than 1 day
        if last_event_date < one_day_ago:
            return one_day_ago

        return last_event_date

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

    def _get_latest_event_timestamp(self, events: list[Activity] | list[Threat] | list[dict]) -> datetime:
        """Searches for the most recent timestamp from a list of events

        Args:
            events (list[Activity] | list[Threat] | list[dict]): List of events to

        Returns:
            datetime: Timestamp of the most recent event of the list
        """
        latest_event_datetime: datetime | None = None
        for event in events:
            event_dict = event if isinstance(event, dict) else event.__dict__
            if event_dict.get("createdAt") is not None:
                if latest_event_datetime is None:
                    latest_event_datetime = datetime.fromisoformat(event_dict["createdAt"])
                else:
                    event_created_at = datetime.fromisoformat(event_dict["createdAt"])
                    if event_created_at > latest_event_datetime:
                        latest_event_datetime = event_created_at

        if latest_event_datetime is None:
            return self._cache_last_event_date
        else:
            return latest_event_datetime

    def pull_events(self):
        raise NotImplementedError

    def next_batch(self):
        # save the starting time
        batch_start_time = time()

        # get the batch
        self.pull_events()

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time()
        batch_duration = int(batch_end_time - batch_start_time)
        logger.debug(f"Fetched and forwarded events in {batch_duration} seconds")
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key, datasource="sentinelone").observe(
            batch_duration
        )

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            logger.debug(f"Next batch in the future. Waiting {delta_sleep} seconds")
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

        self.connector._executor.shutdown(wait=True)


class SentinelOneActivityLogsConsumer(SentinelOneLogsConsumer):
    def pull_events(self):
        """Fetches activities from SentinelOne"""
        # Set  filters
        query_filter = ActivitiesFilter()
        query_filter.apply(key="limit", val=1000)
        query_filter.apply(key="sortBy", val="createdAt")
        query_filter.apply(key="sortOrder", val="asc")

        while self.running:
            # Fetch activities
            activities = self.management_client.activities.get(query_filter)
            logger.debug("activities: received %d events" % len(activities.data))

            INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key, datasource="sentinelone").inc(
                len(activities.data)
            )

            # Push events
            self.connector.push_events_to_intakes(self._serialize_events(activities.data))

            # Update context with latest event date
            latest_event_timestamp = self._get_latest_event_timestamp(activities.data)
            with self.context as cache:
                cache["last_event_date"] = latest_event_timestamp.isoformat()

            # Send Prometheus metrics
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key, datasource="sentinelone").inc(
                len(activities.data)
            )

            if len(activities.data) > 0:
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key, type="activities").set(
                    (datetime.now(UTC) - latest_event_timestamp).total_seconds()
                )

            else:
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key, type="activities").set(0)

            if activities.pagination["nextCursor"] is None:
                break

            query_filter.apply(key="cursor", val=activities.pagination["nextCursor"])


class SentinelOneThreatLogsConsumer(SentinelOneLogsConsumer):
    def pull_events(self):
        """Fetches threats from SentinelOne"""
        query_filter = ThreatQueryFilter()
        query_filter.apply(key="limit", val=1000)
        query_filter.apply(key="sortBy", val="createdAt")
        query_filter.apply(key="sortOrder", val="asc")

        while self.running:
            # Fetch threats
            threats = self.management_client.client.get(endpoint="threats", params=query_filter.filters)
            logger.debug("threats: received %d events" % len(threats.data))

            # Push events
            self.connector.push_events_to_intakes(self._serialize_events(threats.data))

            # Update context with the latest event date
            latest_event_timestamp = self._get_latest_event_timestamp(threats.data)
            with self.context as cache:
                cache["last_event_date"] = latest_event_timestamp.isoformat()

            # Send Prometheus metrics
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key, datasource="sentinelone").inc(
                len(threats.data)
            )

            if len(threats.data) > 0:
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key, type="threats").set(
                    (datetime.now(UTC) - latest_event_timestamp).total_seconds()
                )

            else:
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key, type="threats").set(0)

            if threats.pagination["nextCursor"] is None:
                break

            query_filter.apply(key="cursor", val=threats.pagination["nextCursor"])


CONSUMER_TYPES = {"activity": SentinelOneActivityLogsConsumer, "threat": SentinelOneThreatLogsConsumer}


class SentinelOneLogsConnector(Connector):
    module: SentinelOneModule
    configuration: SentinelOneLogsConnectorConfiguration

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
