import collections
import time
from typing import Any, Deque

import orjson
from sekoia_automation.connector import Connector

from .m365_mixin import EventType, M365Mixin
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS
from .models import VadeSecureConnectorConfiguration


class M365EventsConnector(Connector, M365Mixin):
    configuration: VadeSecureConnectorConfiguration

    def _fetch_events(self) -> None:
        """
        Successively queries the m365 events pages while more are available
        and the current batch is not too big.
        """
        fetch_start_time = time.time()

        for event_type in EventType:
            message_batch: Deque[dict[str, Any]] = collections.deque()
            has_more_message = True

            last_message_date, last_message_id = self.get_event_type_context(event_type)

            self.log(
                message=f"Fetching recent M365 {event_type} messages since {last_message_date}",
                level="debug",
            )

            # save the starting time
            batch_start_time = time.time()

            while has_more_message:
                has_more_message = False
                next_events = self._fetch_next_events(
                    last_message_id=last_message_id,
                    last_message_date=last_message_date,
                    event_type=event_type,
                )
                if next_events:
                    last_message_id = next_events[-1]["id"]
                    last_message_date = self._get_last_message_date(next_events)
                    message_batch.extend(next_events)
                    has_more_message = True

                if len(message_batch) >= self.configuration.chunk_size:
                    break

            if message_batch:
                self.log(
                    message=f"Send a batch of {len(message_batch)} {event_type} messages",
                    level="info",
                )

                INCOMING_MESSAGES.labels(type=event_type, intake_key=self.configuration.intake_key).inc(
                    len(message_batch)
                )

                last_message = message_batch[-1]
                last_message_date = self._get_last_message_date([last_message])
                events_lag = int(time.time() - last_message_date.timestamp())
                EVENTS_LAG.labels(type=event_type, intake_key=self.configuration.intake_key).set(events_lag)

                batch_of_events = [orjson.dumps(event).decode("utf-8") for event in message_batch]
                self.push_events_to_intakes(events=batch_of_events)

                OUTCOMING_EVENTS.labels(type=event_type, intake_key=self.configuration.intake_key).inc(
                    len(batch_of_events)
                )
                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )  # pragma: no cover

            else:
                self.log(
                    message=f"No {event_type} events to forward",
                    level="info",
                )  # pragma: no cover
                EVENTS_LAG.labels(type=event_type, intake_key=self.configuration.intake_key).set(0)

            # get the ending time and compute the duration to fetch the events
            batch_end_time = time.time()
            batch_duration = int(batch_end_time - batch_start_time)
            FORWARD_EVENTS_DURATION.labels(type=event_type, intake_key=self.configuration.intake_key).observe(
                batch_duration
            )

            self.update_event_type_context(last_message_date, last_message_id, event_type)

        fetch_end_time = time.time()
        fetch_duration = fetch_end_time - fetch_start_time
        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - fetch_duration
        if delta_sleep > 0:
            self.log(
                message=f"Next batches in the future. Waiting {delta_sleep} seconds",
                level="debug",
            )  # pragma: no cover
            time.sleep(delta_sleep)
