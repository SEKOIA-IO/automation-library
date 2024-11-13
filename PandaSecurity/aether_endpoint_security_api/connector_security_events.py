import collections
import time
from datetime import datetime
from typing import Deque

import orjson
from sekoia_automation.connector import Connector

from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS
from .security_events_mixin import EVENT_TYPES, SecurityEventsMixin


class AetherSecurityEventsConnector(SecurityEventsMixin, Connector):
    def _fetch_events(self) -> None:
        """
        Successively queries the watchguard aether events pages while more are available
        and the current batch is not too big.
        """
        for event_type, event_type_name in EVENT_TYPES.items():
            # save the starting time
            batch_start_time = time.time()

            message_batch: Deque[dict] = collections.deque()
            has_more_message = True

            last_message_date = self.last_message_date[event_type]

            self.log(
                message=f"Fetching recent Aether '{event_type_name}' messages since {last_message_date}",
                level="info",
            )

            while has_more_message:
                has_more_message = False
                next_events = self._fetch_next_events(last_message_date=last_message_date, event_type=event_type)
                if next_events:
                    last_message_date = self._get_event_date(next_events[-1])
                    message_batch.extend(next_events)
                    has_more_message = True

                if len(message_batch) >= self.max_batch_size:
                    break

            if message_batch:
                INCOMING_MESSAGES.labels(type=event_type_name, intake_key=self.configuration.intake_key).inc(
                    len(message_batch)
                )

                self.log(
                    message=f"Send a batch of {len(message_batch)} {event_type} messages",
                    level="info",
                )

                # compute the events lag
                last_message_timestamp = datetime.strptime(last_message_date, self.RFC3339_STRICT_FORMAT)
                events_lag = (datetime.utcnow() - last_message_timestamp).total_seconds()
                EVENTS_LAG.labels(type=event_type_name, intake_key=self.configuration.intake_key).set(events_lag)

                batch_of_events = [orjson.dumps(event).decode("utf-8") for event in message_batch]
                self.push_events_to_intakes(batch_of_events)

                OUTCOMING_EVENTS.labels(type=event_type_name, intake_key=self.configuration.intake_key).inc(
                    len(message_batch)
                )

            else:
                self.log(
                    message=f"No {event_type_name} events to forward",
                    level="info",
                )
                EVENTS_LAG.labels(type=event_type_name, intake_key=self.configuration.intake_key).set(0)

            # get the ending time and compute the duration to fetch the events
            batch_end_time = time.time()
            batch_duration = int(batch_end_time - batch_start_time)
            FORWARD_EVENTS_DURATION.labels(type=event_type_name, intake_key=self.configuration.intake_key).observe(
                batch_duration
            )

            self.log(
                message=f"Set last_message_date for Aether '{event_type_name}' to {last_message_date}",
                level="info",
            )
            self.last_message_date[event_type] = last_message_date
