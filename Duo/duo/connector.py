import datetime
import time
from functools import cached_property
from threading import Event, Lock, Thread
from typing import Optional

import duo_client
import orjson
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import DuoModule, LogType
from .iterators import AdminLogsIterator, AuthLogsIterator, OfflineLogsIterator, TelephonyLogsIterator
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class AdminLogsConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    chunk_size: int = 1000


class DuoLogsConsumer(Thread):
    """
    Each endpoint of Duo Admin API is consumed in its own separate thread.
    """

    def __init__(self, connector: "DuoAdminLogsConnector", log_type: LogType, checkpoint: Optional[dict] = None):
        super().__init__()

        self.connector = connector

        self._stop_event = Event()
        self._log_type = log_type

        self.last_checkpoint = checkpoint or {}

        self.frequency = self.connector.configuration.frequency
        self.chunk_size = self.connector.configuration.chunk_size

    def log(self, *args, **kwargs):
        self.connector.log(*args, **kwargs)

    @property
    def log_label(self):
        return self._log_type.name

    def stop(self):
        self._stop_event.set()

    @property
    def running(self):
        return not self._stop_event.is_set()

    @cached_property
    def client(self):
        return duo_client.Admin(
            ikey=self.connector.module.configuration.integration_key,
            skey=self.connector.module.configuration.secret_key,
            host=self.connector.module.configuration.hostname,
        )

    def load_checkpoint(self):
        self.connector.context_lock.acquire()

        with self.connector.context as cache:
            default_min_time = int(time.time()) - 5 * 60  # start with events from 5 min ago

            # these are using milliseconds instead of seconds
            if self._log_type in (LogType.AUTHENTICATION, LogType.TELEPHONY):
                default_min_time *= 1000

            result = cache.get(self._log_type.value, {"min_time": default_min_time, "next_offset": None})

        self.connector.context_lock.release()

        return result

    def save_checkpoint(self, **offset):
        key = self._log_type.value

        self.connector.context_lock.acquire()

        with self.connector.context as cache:
            cache[key] = offset

        self.connector.context_lock.release()

    def get_events_iterator(self):
        last_checkpoint = self.load_checkpoint()

        if self._log_type == LogType.ADMINISTRATION:
            min_time = last_checkpoint.get("min_time")

            return AdminLogsIterator(
                client=self.client, min_time=min_time, limit=self.chunk_size, callback=self.save_checkpoint
            )

        elif self._log_type == LogType.AUTHENTICATION:
            min_time = last_checkpoint.get("min_time")
            next_offset = last_checkpoint.get("next_offset")

            return AuthLogsIterator(
                client=self.client,
                min_time=min_time,
                limit=self.chunk_size,
                next_offset=next_offset,
                callback=self.save_checkpoint,
            )

        elif self._log_type == LogType.TELEPHONY:
            min_time = last_checkpoint.get("min_time")
            next_offset = last_checkpoint.get("next_offset")

            return TelephonyLogsIterator(
                client=self.client,
                min_time=min_time,
                limit=self.chunk_size,
                next_offset=next_offset,
                callback=self.save_checkpoint,
            )

        elif self._log_type == LogType.OFFLINE:
            min_time = last_checkpoint.get("min_time")

            return OfflineLogsIterator(
                client=self.client, min_time=min_time, limit=self.chunk_size, callback=self.save_checkpoint
            )

        raise NotImplementedError(f"Unsupported log type {self._log_type}")

    def fetch_batches(self):
        total_num_of_events = 0

        # Fetch next batch
        for events in self.get_events_iterator():
            batch_start_time = time.time()

            if len(events) > 0:
                if self._log_type == LogType.TELEPHONY:
                    # Telephony logs have their datetime represented as "2023-03-21T22:34:49.466370+00:00"
                    most_recent_event = max(events, key=lambda item: item["ts"])
                    most_recent_timestamp = datetime.datetime.fromisoformat(most_recent_event["ts"]).timestamp()
                else:
                    most_recent_event = max(events, key=lambda item: item["timestamp"])
                    most_recent_timestamp = most_recent_event["timestamp"]

                current_timestamp = int(time.time())
                events_lag = current_timestamp - most_recent_timestamp
                EVENTS_LAG.labels(intake_key=self.connector.configuration.intake_key, type=self._log_type.value).set(
                    events_lag
                )

            # Add `eventtype` field
            for event in events:
                event.update({"eventtype": self._log_type})

            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in events]
            INCOMING_MESSAGES.labels(
                intake_key=self.connector.configuration.intake_key, type=self._log_type.value
            ).inc(len(batch_of_events))

            # if the batch is full, push it
            if len(batch_of_events) > 0:
                self.connector.push_events_to_intakes(events=batch_of_events)

            total_num_of_events += len(events)

            # get the ending time and compute the duration to fetch the events
            batch_end_time = time.time()
            batch_duration = int(batch_end_time - batch_start_time)
            self.log(
                message=f"Fetched and forwarded {len(batch_of_events)} {self.log_label} events"
                f" in {batch_duration} seconds",
                level="info",
            )

            OUTCOMING_EVENTS.labels(intake_key=self.connector.configuration.intake_key, type=self._log_type.value).inc(
                len(events)
            )

            FORWARD_EVENTS_DURATION.labels(
                intake_key=self.connector.configuration.intake_key, type=self._log_type.value
            ).observe(batch_duration)

            # compute the remaining sleeping time. If greater than 0, sleep
            delta_sleep = self.frequency - batch_duration
            if delta_sleep > 0:
                self.log(
                    message=f"Next batch of {self.log_label} events in the future. " f"Waiting {delta_sleep} seconds",
                    level="info",
                )
                time.sleep(delta_sleep)

        if total_num_of_events == 0:
            time_to_sleep = self.frequency
            self.log(message=f"No new {self.log_label} events. Waiting {time_to_sleep} seconds", level="info")
            time.sleep(time_to_sleep)

    def run(self):
        try:
            while self.running:
                self.fetch_batches()

        except Exception as error:
            self.connector.log_exception(error, message=f"Failed to forward {self.log_label} events")


class DuoAdminLogsConnector(Connector):
    module: DuoModule
    configuration: AdminLogsConnectorConfiguration

    LOGS_TO_FETCH = (LogType.AUTHENTICATION, LogType.ADMINISTRATION, LogType.TELEPHONY, LogType.OFFLINE)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.context = PersistentJSON("context.json", self._data_path)
        self.context_lock = Lock()
        self.consumers = {}

    def start_consumers(self):
        consumers = {}
        for log_type in self.LOGS_TO_FETCH:
            self.log(message=f"Start {log_type.name} consumer", level="info")
            consumers[log_type] = DuoLogsConsumer(connector=self, log_type=log_type)
            consumers[log_type].start()

        return consumers

    def supervise_consumers(self, consumers):
        for log_type, consumer in consumers.items():
            if consumer is None or (not consumer.is_alive() and consumer.running):
                self.log(message=f"Restarting {log_type.name} consumer", level="info")

                consumers[log_type] = DuoLogsConsumer(connector=self, log_type=log_type)
                consumers[log_type].start()

    def stop_consumers(self, consumers):
        for name, consumer in consumers.items():
            if consumer is not None and consumer.is_alive():
                self.log(message=f"Stopping {name.name} consumer", level="info")
                consumer.stop()

    def run(self):
        consumers = self.start_consumers()

        while self.running:
            self.supervise_consumers(consumers)
            time.sleep(5)

        self.stop_consumers(consumers)
