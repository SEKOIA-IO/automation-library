import collections
import time
import uuid
from collections.abc import Generator, Sequence
from datetime import datetime, timedelta
from typing import Deque
from urllib.parse import urljoin

import orjson
import requests
from dateutil import parser
from dateutil.parser import ParserError
from sekoia_automation.trigger import Trigger

from vadesecure_modules import VadeSecureModule
from vadesecure_modules.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS
from vadesecure_modules.models import VadeSecureTriggerConfiguration

EVENT_TYPES: list[str] = ["emails", "remediations/auto", "remediations/manual"]


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.http_session = requests.Session()
        self.api_credentials: dict | None = None

    def initializing(self):
        self.last_message_id: dict[str, str] = {event_type: "" for event_type in EVENT_TYPES}
        self.last_message_date: dict[str, datetime] = {
            event_type: (datetime.utcnow() - timedelta(minutes=1)) for event_type in EVENT_TYPES
        }
        self.pagination_limit = 100
        self.max_batch_size = self.configuration.chunk_size
        self.log(message="M365 Events Trigger has started", level="info")

    def run(self):
        self.initializing()

        while True:
            try:
                self._fetch_events()
            except Exception as ex:
                self.log_exception(ex, message="An unknown exception occurred")
                raise

            time.sleep(self.configuration.frequency)

    def _chunk_events(self, events: Sequence, chunk_size: int) -> Generator[list, None, None]:
        """
        Group events by chunk
        :param sequence events: The events to group
        :param int chunk_size: The size of the chunk
        """
        chunk: list = []

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

    def _send_emails(self, emails: list, event_name: str):
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
        for event_type in EVENT_TYPES:
            message_batch: Deque[dict] = collections.deque()
            has_more_message = True

            last_message_id = self.last_message_id[event_type]
            last_message_date = self.last_message_date[event_type]

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

                if len(message_batch) >= self.max_batch_size:
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
                EVENTS_LAG.labels(type=event_type).observe(events_lag)

                for emails in self._chunk_events(list(message_batch), self.max_batch_size):
                    self._send_emails(
                        emails=list(emails),
                        event_name=f"M365-events_{last_message_date}",
                    )

                OUTCOMING_EVENTS.labels(type=event_type).inc(len(message_batch))

            # get the ending time and compute the duration to fetch the events
            batch_end_time = time.time()
            batch_duration = int(batch_end_time - batch_start_time)
            FORWARD_EVENTS_DURATION.labels(type=event_type).observe(batch_duration)

            self.last_message_id[event_type] = last_message_id
            self.last_message_date[event_type] = last_message_date

    def _fetch_next_events(self, last_message_id: str, last_message_date: datetime, event_type: str) -> list[dict]:
        """
        Returns the next page of events produced by M365
        """
        if event_type not in EVENT_TYPES:
            raise TypeError

        # no need to fetch events from more than 1 hour
        # it happens when last received event was more than one hour ago
        if last_message_date < datetime.utcnow() - timedelta(hours=1):
            last_message_date = datetime.utcnow() - timedelta(hours=1)

        payload_json = {
            "limit": self.pagination_limit,
            "sort": [{"date": "asc"}, "id"],
            "search_after": [
                last_message_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                last_message_id,
            ],
        }

        url = urljoin(
            base=self.module.configuration.api_host,
            url=f"/api/v1/tenants/{self.configuration.tenant_id}/logs/{event_type}/search",
        )

        response = self.http_session.post(
            url=url,
            json=payload_json,
            headers={"Authorization": self._get_authorization()},
        )
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
            if event_type == "emails":
                return response.json()["result"]["messages"]
            else:
                return response.json()["result"]["campaigns"]

    def _get_authorization(self) -> str:
        """
        Returns the access token and uses the OAuth2 to compute it if required
        """

        if (
            self.api_credentials is None
            or datetime.utcnow() + timedelta(seconds=300) >= self.api_credentials["expires_in"]
        ):
            current_dt = datetime.utcnow()
            response = self.http_session.post(
                url=self.module.configuration.oauth2_authorization_url,
                data={
                    "grant_type": "client_credentials",
                    "scope": "m365.api.read",
                    "client_id": self.module.configuration.client_id,
                    "client_secret": self.module.configuration.client_secret,
                },
            )
            if not response.ok:
                self.log(
                    f"OAuth2 server responded {response.status_code} - {response.reason}",
                    level="error",
                )
            response.raise_for_status()

            api_credentials: dict = response.json()
            # convert expirations into datetime
            api_credentials["expires_in"] = current_dt + timedelta(seconds=api_credentials["expires_in"])
            self.api_credentials = api_credentials

        return f"{self.api_credentials['token_type'].title()} {self.api_credentials['access_token']}"

    def _get_last_message_date(self, events: list) -> datetime:
        for event in reversed(events):
            try:
                # Make the date timezone naive to support comparison with datetime.utcnow()
                return parser.parse(event["date"]).replace(tzinfo=None)
            except (ParserError, KeyError):
                self.log(message="Failed to parse event date", level="error")
        raise ValueError("No event had a valid date")
