import datetime
import threading
import time
from typing import Callable
from ciso8601 import parse_datetime_as_naive

from pydantic import BaseModel


class Fingerprint(BaseModel):
    condition_func: Callable[[dict], bool]
    build_hash_str_func: Callable[[dict], str]


class Aggregation(BaseModel):
    start: datetime.datetime
    end: datetime.datetime
    count: int
    event: dict

    def get_aggregated_event(self):
        aggregated_event = self.event
        aggregated_event["event"]["start"] = self.start.isoformat()
        aggregated_event["event"]["end"] = self.start.isoformat()
        aggregated_event["event"]["count"] = self.count
        return aggregated_event


class EventAggregatorTTLThread(threading.Thread):
    f_must_stop: bool  # thread will stop if this flag is active
    ttl: int  # ttl value
    on_flush_func: Callable[[dict], None]  # function to be call when aggregation is flushed

    def __init__(
        self,
        event_aggregator: "EventAggregator",
        ttl: int,
        on_flush_func: Callable[[dict], None],
        delay: float = 10,
    ):
        super().__init__()
        self.event_aggregator = event_aggregator
        self.f_must_stop = False
        self.ttl = ttl
        self.on_flush_func = on_flush_func
        self.delay = delay

    def stop(self) -> None:
        self.f_must_stop = True

    def run(self) -> None:
        try:
            while not self.f_must_stop:
                time.sleep(self.delay)
                for aggregated_event in self.event_aggregator.flush_all_ttl(ttl=self.ttl):
                    self.on_flush_func(aggregated_event)
        finally:
            for aggregated_event in self.event_aggregator.flush_all():
                self.on_flush_func(aggregated_event)


class EventAggregator:
    ttl_thread: EventAggregatorTTLThread | None
    lock: threading.Lock

    def __init__(self, aggregation_definitions: dict[str, list[Fingerprint]]):
        self.aggregation_definitions = aggregation_definitions
        self.aggregations: dict[str, Aggregation] = dict()
        self.lock = threading.Lock()

    def start_flush_on_ttl(self, ttl: int, on_flush_func: Callable[[dict], None], delay: float = 10):
        """
        This method MUST be called to trigger the execution of the ttl thread
        """
        self.ttl_thread = EventAggregatorTTLThread(
            event_aggregator=self, ttl=ttl, on_flush_func=on_flush_func, delay=delay
        )
        self.ttl_thread.start()

    def stop(self):
        """
        This method is only meant to stop the ttl thread
        """
        if self.ttl_thread:
            self.ttl_thread.stop()
            self.ttl_thread.join()

    def flush_all(self) -> list[dict]:
        """
        returns all the aggregated events and remove them from the ongoing aggregations
        """
        aggregated_events = []

        # we prevent any actions on the aggregations while flushing
        with self.lock:
            for aggregation in self.aggregations.values():
                if aggregation.count > 0:
                    aggregated_events.append(aggregation.get_aggregated_event())

            self.aggregations = dict()
        return aggregated_events

    def flush_all_ttl(self, ttl: int) -> list[dict]:
        """
        Returns (and delete) all the events we aggregate for at least the ttl time
        """
        event_hashes_to_flush = []
        aggregated_events = []
        # we prevent any actions on the aggregations while flushing
        with self.lock:
            for event_hash, aggregation in self.aggregations.items():
                if aggregation.start + datetime.timedelta(seconds=ttl) < datetime.datetime.utcnow():
                    event_hashes_to_flush.append(event_hash)

                    if aggregation.count > 0:
                        aggregated_events.append(aggregation.get_aggregated_event())

            for event_hash in event_hashes_to_flush:
                del self.aggregations[event_hash]

        return aggregated_events

    def get_hash(self, event: dict) -> str | None:
        """
        Returns the hash to fingerprint the specified event
        """
        event_dialect_uuid = event["sekoiaio"]["intake"]["dialect_uuid"]

        for fingerprint in self.aggregation_definitions.get(event_dialect_uuid, []):
            if fingerprint.condition_func(event):
                return f"{event_dialect_uuid};{fingerprint.build_hash_str_func(event)}"
        return None

    def aggregate(self, event: dict) -> dict | None:
        try:
            event_hash = self.get_hash(event)
            # if no hash can be computed, we don't aggregate and forward the event
            if not event_hash:
                return event

            # the aggregation stores the parsed timestamp
            event_dt = parse_datetime_as_naive(event["@timestamp"])

            # if hash is already known
            with self.lock:
                if event_hash in self.aggregations:
                    # update the aggregation's counter and last seen
                    self.aggregations[event_hash].count += 1
                    self.aggregations[event_hash].end = event_dt

                    # event is aggregated, we don't want to forward it
                    return None

                # if hash is unknown
                else:
                    # create a new aggregation with event details
                    self.aggregations[event_hash] = Aggregation(
                        event=event,
                        start=event_dt,
                        end=event_dt,
                        count=0
                        # =0 to prevent replay on flushing because we already send first occurrence of the event
                    )
                    # forward the first occurrence of the aggregation
                    return event
        except Exception as any_exception:
            print(any_exception)

        return event
