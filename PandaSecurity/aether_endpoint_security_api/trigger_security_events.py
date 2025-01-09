import collections
from typing import Deque

from .security_events_mixin import EVENT_TYPES, SecurityEventsMixin


class AetherSecurityEventsTrigger(SecurityEventsMixin):
    def _fetch_events(self) -> None:
        """
        Successively queries the watchguard aether events pages while more are available
        and the current batch is not too big.
        """
        for event_type, event_type_name in EVENT_TYPES.items():
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
                self.log(
                    message=f"Send a batch of {len(message_batch)} {event_type} messages",
                    level="info",
                )

                self.send_event(
                    event_name=f"Aether-events_{last_message_date}",
                    event={"events": list(message_batch)},
                )

            self.log(
                message=f"Set last_message_date for Aether '{event_type_name}' to {last_message_date}",
                level="info",
            )
            self.last_message_date[event_type] = last_message_date
