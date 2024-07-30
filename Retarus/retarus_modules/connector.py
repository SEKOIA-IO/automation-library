import os
import queue
import time
from typing import Any, Optional

from sekoia_automation.connector import Connector

from retarus_modules.configuration import RetarusConfig
from retarus_modules.consumer import RetarusEventsConsumer
from retarus_modules.metrics import OUTGOING_EVENTS


class RetarusConnector(Connector):
    configuration: RetarusConfig

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        super().__init__(*args, **kwargs)

        # create the events queue
        self.events_queue: queue.Queue = queue.Queue(maxsize=int(os.environ.get("QUEUE_SIZE", 10000)))

        # Arguments for the polling of events from the queue
        self.queue_get_limit = 10
        self.queue_get_timeout = 0.1
        self.queue_get_block = True
        self.queue_get_retries = 10

    def run(self):  # pragma: no cover
        self.log(message="Retarus Events Trigger has started", level="info")

        # start the consumer
        consumer = RetarusEventsConsumer(self.configuration, self.events_queue, self.log, self.log_exception)
        consumer.start()

        while self.running:
            # if the consumer is dead, we spawn a new one
            if not consumer.is_alive() and consumer.is_running:
                self.log(message="Restart event consumer", level="warning")
                consumer = RetarusEventsConsumer(self.configuration, self.events_queue, self.log, self.log_exception)
                consumer.start()

            # Send events to Symphony
            events = self._queue_get_batch()
            if len(events) > 0:
                self.log(
                    message="Forward an event to the intake",
                    level="info",
                )
                OUTGOING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(events))
                self.push_events_to_intakes(events=events)

            # Wait 5 seconds for the next supervision
            time.sleep(5)

        # Stop the consumer
        if consumer.is_alive():
            consumer.stop()
            consumer.join(timeout=2)

        # Stop the connector executor
        self._executor.shutdown(wait=True)

    def _queue_get_batch(self) -> list[str]:
        """Gets a batch of events from the queue

        Several parameters for these batches can be set when initializing the class:
        * queue_get_limit is the max number of messages we want to get for a match
        * queue_get_retries is the max number of retries (empty queue exception) we accept for a given batch
        * queue_get_block is the block parameter of queue.get
        * queue_get_timeout is the timeout parameter of queue.get

        Returns:
            Events we got from the queue
        """
        result: list[str] = []
        i: int = 0
        while len(result) < self.queue_get_limit and i < self.queue_get_retries:
            try:
                result.append(self.events_queue.get(block=self.queue_get_block, timeout=self.queue_get_timeout))
            except queue.Empty:
                i += 1
                self.log(message="Empty queue", level="DEBUG")
                continue
        return result
