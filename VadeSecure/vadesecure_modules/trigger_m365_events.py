import collections
import time
import uuid
from collections.abc import Generator, Sequence
from datetime import datetime, timedelta
from enum import Enum
from functools import cached_property
from posixpath import join as urljoin
from typing import Any, Deque, Tuple

import orjson
import requests
from dateutil import parser
from dateutil.parser import ParserError, isoparse
from sekoia_automation.storage import PersistentJSON
from sekoia_automation.trigger import Trigger

from vadesecure_modules import VadeSecureModule
from vadesecure_modules.client import ApiClient
from vadesecure_modules.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS
from vadesecure_modules.models import VadeSecureTriggerConfiguration


class EventType(Enum):
    EMAILS = "emails"
    REMEDIATIONS_AUTO = "remediations/auto"
    REMEDIATIONS_MANUAL = "remediations/manual"


class M365EventsTrigger(Trigger):
    """
    The M365Events trigger reads the next batch of messages exposed by the VadeSecure
    dedicated APIs and forward it to the playbook run.

    Quick notes
    - Authentication on API is OAuth2 and access token expiration is handled.
    - Pagination relies on local instance variables {last_message_id} and {last_message_date},
      hence last_message pointer is lost when the trigger stops.
    - A margin of 300sec is added to the expiration date of oauth2 token.
    """

    module: VadeSecureModule
    configuration: VadeSecureTriggerConfiguration
    _http_session: requests.Session | None = None

    def __init__(self, *args: Any, **kwargs: dict[str, Any]) -> None:
        super().__init__(*args, **kwargs)

        self.api_credentials: dict[str, Any] | None = None
        self.context = PersistentJSON("context.json", self._data_path)

    @cached_property
    def client(self) -> ApiClient:
        try:
            return ApiClient(
                auth_url=self.module.configuration.oauth2_authorization_url,
                client_id=self.module.configuration.client_id,
                client_secret=self.module.configuration.client_secret,
            )

        except requests.exceptions.HTTPError as error:
            response = error.response
            self.log(
                f"OAuth2 server responded {response.status_code} - {response.reason}",
                level="error",
            )
            raise error

        except TimeoutError as error:
            self.log(message="Failed to authorize due to timeout", level="error")
            raise error

    def get_event_type_context(self, event_type: EventType) -> Tuple[datetime, str | None]:
        """
        Get last event date and id.

        Returns:
            Tuple[datetime, str | None]:
        """
        # no need to fetch events from more than 1 hour
        # it happens when last received event was more than one hour ago
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        with self.context as cache:
            event_type_context = cache.get(event_type.value)
            if not event_type_context:
                event_type_context = {}

            last_message_date_str = event_type_context.get("last_message_date")
            last_message_id = event_type_context.get("last_message_id")

            if last_message_date_str is None:
                return one_hour_ago, last_message_id

            last_event_date = isoparse(last_message_date_str)

            if last_event_date < one_hour_ago:
                return one_hour_ago, last_message_id

            return last_event_date, last_message_id

    def update_event_type_context(
        self, last_message_date: datetime, last_message_id: str | None, event_type: EventType
    ) -> None:
        """
        Set last event date.

        Args:
            last_message_date: datetime
            last_message_id: str
            event_type: EventType
        """
        with self.context as cache:
            cache[event_type.value] = {"last_message_date": last_message_date.isoformat()}

            if last_message_id:
                cache[event_type.value]["last_message_id"] = last_message_id

    def run(self) -> None:  # pragma: no cover
        """Run the trigger."""
        while True:
            try:
                self._fetch_events()
            except Exception as ex:
                self.log_exception(ex, message="An unknown exception occurred")
                raise

            time.sleep(self.configuration.frequency)

    def _chunk_events(self, events: Sequence[Any], chunk_size: int) -> Generator[list[Any], None, None]:
        """
        Group events by chunk
        :param sequence events: The events to group
        :param int chunk_size: The size of the chunk
        """
        chunk: list[Any] = []

        # iter over the events
        for event in events:
            # if the chnuk is full
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

                INCOMING_MESSAGES.labels(type=event_type).inc(len(message_batch))

                last_message = message_batch[-1]
                last_message_date = self._get_last_message_date([last_message])
                events_lag = int(time.time() - last_message_date.timestamp())
                EVENTS_LAG.labels(type=event_type).set(events_lag)

                for emails in self._chunk_events(list(message_batch), self.configuration.chunk_size):
                    self._send_emails(
                        emails=list(emails),
                        event_name=f"M365-events_{last_message_date}",
                    )

                OUTCOMING_EVENTS.labels(type=event_type).inc(len(message_batch))

            # get the ending time and compute the duration to fetch the events
            batch_end_time = time.time()
            batch_duration = int(batch_end_time - batch_start_time)
            FORWARD_EVENTS_DURATION.labels(type=event_type).observe(batch_duration)

            self.update_event_type_context(last_message_date, last_message_id, event_type)

    def _fetch_next_events(
        self, last_message_id: str | None, last_message_date: datetime, event_type: EventType
    ) -> list[dict[str, Any]]:
        """
        Returns the next page of events produced by M365
        """
        payload_json = {
            "limit": self.configuration.pagination_limit,
            "sort": [{"date": "asc"}, "id"],
            "search_after": [last_message_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), last_message_id or ""],
        }

        url = urljoin(
            self.module.configuration.api_host.rstrip("/"),
            f"api/v1/tenants/{self.configuration.tenant_id}/logs/{event_type.value}/search",
        )

        response = self.client.post(url=url, json=payload_json, timeout=60)

        if not response.ok:
            # Exit trigger if we can't authenticate against the server
            level = "critical" if response.status_code in [401, 403] else "error"
            self.log(
                message=(
                    f"Request on M365 API to fetch events of tenant {self.configuration.tenant_id} "
                    f"failed with status {response.status_code} - {response.reason}"
                ),
                level=level,
            )

            return []
        else:
            result: list[dict[str, Any]] = (
                response.json()["result"]["messages"]
                if event_type == EventType.EMAILS
                else response.json()["result"]["campaigns"]
            )

            return result

    def _get_last_message_date(self, events: list[Any]) -> datetime:
        for event in reversed(events):
            try:
                # Make the date timezone naive to support comparison with datetime.utcnow()
                return parser.parse(event["date"]).replace(tzinfo=None)
            except (ParserError, KeyError):
                self.log(message="Failed to parse event date", level="error")
        raise ValueError("No event had a valid date")
