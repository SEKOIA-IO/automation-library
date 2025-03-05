import collections
import time
import uuid
from typing import Any, Deque, Generator, Sequence

import orjson

from vadesecure_modules.m365_mixin import EventType, M365Mixin


class M365EventsTrigger(M365Mixin):
    """
    The M365Events trigger reads the next batch of messages exposed by the VadeSecure
    dedicated APIs and forward it to the playbook run.

    Quick notes
    - Authentication on API is OAuth2 and access token expiration is handled.
    - Pagination relies on local instance variables {last_message_id} and {last_message_date},
      hence last_message pointer is lost when the trigger stops.
    - A margin of 300sec is added to the expiration date of oauth2 token.
    """

    def _chunk_events(self, events: Sequence[Any], chunk_size: int) -> Generator[list[Any], None, None]:
        """
        Group events by chunk
        :param sequence events: The events to group
        :param int chunk_size: The size of the chunk
        """
        chunk: list[Any] = []

        # iter over the events
        for event in events:
            # if the chunk is full
            if len(chunk) >= chunk_size:
                # yield the current chunk and create a new one
                yield chunk
                chunk = []

            # add the event to the current chunk
            chunk.append(event)

        # if the last chunk is not empty
        if len(chunk) > 0:
            # yield the last chunk
            yield chunk

    def _send_emails(self, emails: list[dict[str, Any]], event_name: str) -> None:
        # save event in file
        work_dir = self.data_path.joinpath("vadesecure_m365_events").joinpath(str(uuid.uuid4()))
        work_dir.mkdir(parents=True, exist_ok=True)

        event_path = work_dir.joinpath("event.json")
        with event_path.open("w") as fp:
            fp.write(orjson.dumps(emails).decode("utf-8"))

        # Send Event
        directory = str(work_dir.relative_to(self.data_path))
        file_path = str(event_path.relative_to(work_dir))
        self.send_event(
            event_name=event_name,
            event={"emails_path": file_path},
            directory=directory,
            remove_directory=True,
        )

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

                last_message = message_batch[-1]
                last_message_date = self._get_last_message_date([last_message])

                for emails in self._chunk_events(list(message_batch), self.configuration.chunk_size):
                    self._send_emails(
                        emails=list(emails),
                        event_name=f"M365-events_{last_message_date}",
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
