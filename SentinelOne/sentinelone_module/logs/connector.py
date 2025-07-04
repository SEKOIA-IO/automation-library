import json
from datetime import UTC, datetime, timedelta
from functools import cached_property
from pathlib import Path
from threading import Event, Lock, Thread
from time import sleep, time

from cachetools import Cache, LRUCache
from management.mgmtsdk_v2.client import ManagementResponse
from management.mgmtsdk_v2.entities.activity import Activity
from management.mgmtsdk_v2.entities.threat import Threat
from management.mgmtsdk_v2.exceptions import SentinelBaseException, UnauthorizedException
from management.mgmtsdk_v2.services.activity import ActivitiesFilter
from management.mgmtsdk_v2.services.threat import ThreatQueryFilter
from management.mgmtsdk_v2_1.mgmt import Management
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import Connector

from sentinelone_module.base import SentinelOneModule
from sentinelone_module.exceptions import SENTINEL_ONE_EMPTY_RESPONSE, SentinelOneManagementResponseError
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
            path=self.get_data_path(consumer_type),
            start_at=timedelta(days=1),
            ignore_older_than=timedelta(days=1),
            lock=self.connector.context_lock,
        )
        self.from_date = self.cursor.offset
        self.session_events_cache: Cache = self.load_events_cache()

    def get_data_path(self, consumer_type: str) -> Path:
        # TEMPORARY SOLUTION ONLY!
        #
        # Checkpoint uses data path under the hood like below:
        # PersistentJSON("context.json", path)
        #
        # Where `path` is the data path of the connector
        # As we want to split checkpoints by consumer type we should perform transitional migration
        #
        # So if result_path does not exists, we should copy the context.json file into it
        result_path = self.connector.data_path / consumer_type
        new_context = result_path / "context.json"
        if not result_path.exists():
            logger.info("Migrating context file for consumer type", consumer_type=consumer_type)
            result_path.mkdir(parents=True, exist_ok=True)
            old_context = self.connector.data_path / "context.json"
            if old_context.exists():
                with old_context.open("r") as old_file:
                    with new_context.open("w") as new_file:
                        new_file.write(old_file.read())

        logger.info("Checkpoint path for consumer", consumer_type=consumer_type, path=result_path)
        return result_path

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
        events_cache: LRUCache = LRUCache(maxsize=10000) # Update cache size to 10_000

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

        # Handling specific HTTP status
        except SentinelBaseException as e:
            self.log_exception(e, message=f"Error occurred while fetching events from SentinelOne API: {e}")

        except SentinelOneManagementResponseError as e:
            self.log_exception(e, message=e.message)

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
        self.batch_size = min(
            max(self.connector.configuration.activities_batch_size, 100),  # Minimum batch size
            1000,  # Maximum batch size
        )  # Number of activities to fetch per request

    def pull_events(self, last_timestamp: datetime | None) -> list:
        """Fetches activities from SentinelOne"""
        # Set  filters
        query_filter = ActivitiesFilter()
        query_filter.apply(key="limit", val=self.batch_size)
        query_filter.apply(key="sortBy", val="createdAt")
        query_filter.apply(key="sortOrder", val="asc")

        if last_timestamp:
            query_filter.apply(key="createdAt", val=last_timestamp.isoformat(), op="gt")

        events_ids = []
        while self.running:
            # Fetch activities
            activities_response: ManagementResponse | None = self.management_client.activities.get(query_filter)
            if activities_response is None:
                raise SENTINEL_ONE_EMPTY_RESPONSE

            SentinelOneManagementResponseError.create_and_raise(activities_response)

            # data can be None
            activities = activities_response.data or []
            nb_activities = len(activities)
            logger.debug("Collected activities", nb=nb_activities)
            if nb_activities == 0:
                break

            INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(nb_activities)

            # discard already collected events
            selected_events = filter_collected_events(
                activities, lambda activity: activity.id, self.session_events_cache
            )

            # Push events
            if len(selected_events) > 0:
                events_ids.extend(self.connector.push_events_to_intakes(self._serialize_events(selected_events)))

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

            if activities_response.pagination["nextCursor"] is None:
                break

            query_filter.apply(key="cursor", val=activities_response.pagination["nextCursor"])

        return events_ids


class SentinelOneThreatLogsConsumer(SentinelOneLogsConsumer):
    def __init__(self, connector: "SentinelOneLogsConnector"):
        super().__init__(connector, "threat")
        self.batch_size = min(
            max(self.connector.configuration.threats_batch_size, 1), 1000  # Minimum batch size  # Maximum batch size
        )  # Number of threats to fetch per request

    def pull_events(self, last_timestamp: datetime | None):
        """Fetches threats from SentinelOne"""
        query_filter = ThreatQueryFilter()

        query_filter.apply(key="limit", val=self.batch_size)
        query_filter.apply(key="sortBy", val="createdAt")
        query_filter.apply(key="sortOrder", val="asc")

        if last_timestamp:
            query_filter.apply(key="createdAt", val=last_timestamp.isoformat(), op="gt")

        events_ids = []
        while self.running:
            # Fetch threats
            threat_response: ManagementResponse | None = self.management_client.client.get(
                endpoint="threats", params=query_filter.filters
            )

            if threat_response is None:
                raise SENTINEL_ONE_EMPTY_RESPONSE

            SentinelOneManagementResponseError.create_and_raise(threat_response)

            # data can be None
            threats = threat_response.data or []
            nb_threats = len(threats)
            logger.debug("Collected nb_threats", nb=nb_threats)
            if nb_threats == 0:
                break

            # discard already collected events
            selected_events = filter_collected_events(threats, lambda threat: threat["id"], self.session_events_cache)

            # Push events
            if len(selected_events) > 0:
                events_ids.extend(self.connector.push_events_to_intakes(self._serialize_events(selected_events)))

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

            if threat_response.pagination["nextCursor"] is None:
                break

            query_filter.apply(key="cursor", val=threat_response.pagination["nextCursor"])

        return events_ids


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
