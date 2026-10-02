import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Any, Generator

import orjson
import requests
from cachetools import Cache, LRUCache
from dateutil.parser import isoparse
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from office365.metrics import FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS

from .client import ApiClient
from .client.auth import AuthenticationError
from .timestepper import TimeStepper


class O365Config(DefaultConnectorConfiguration):
    client_id: str
    client_secret: str
    tenant_id: str

    frequency: int = 60
    timedelta: int = 5
    start_time: int = 1


class Office365MessageTraceTriggerGraphAPI(Connector):
    configuration: O365Config

    RFC3339_STRICT_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.scopes: list = ["https://graph.microsoft.com/.default"]
        self.context = PersistentJSON("context.json", self.data_path)

        self.cache_size = 2000
        self.events_cache: Cache[str, bool] = self.load_events_cache()

    def load_events_cache(self) -> Cache[str, bool]:
        """
        Load the events cache.
        """
        cache: Cache[str, bool] = LRUCache(maxsize=self.cache_size)

        with self.context as context:
            # load the cache from the context
            events_cache = context.get("events_cache", [])

        for uuid in events_cache:
            cache[uuid] = True

        return cache

    def save_events_cache(self) -> None:
        """
        Save the events cache.
        """
        with self.context as context:
            # save the events cache to the context
            context["events_cache"] = list(self.events_cache.keys())

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            tenant_id=self.configuration.tenant_id,
            client_id=self.configuration.client_id,
            client_secret=self.configuration.client_secret,
            scopes=self.scopes,
        )

    @cached_property
    def stepper(self) -> TimeStepper:
        with self.context as cache:
            most_recent_date_requested_str = cache.get("most_recent_date_requested")

            if most_recent_date_requested_str is None:
                return TimeStepper.create(
                    self,
                    self.configuration.frequency,
                    self.configuration.timedelta,
                    self.configuration.start_time,
                )

            # parse the most recent requested date
            most_recent_date_requested = isoparse(most_recent_date_requested_str)

            # We don't retrieve messages older than 30 days
            # see https://learn.microsoft.com/en-us/previous-versions/office/developer/o365-enterprise-developers/↵
            # jj984335(v=office.15)?redirectedfrom=MSDN#data-granularity-persistence-and-availability
            now = datetime.now(timezone.utc)
            one_month_ago = now - timedelta(days=30)
            if most_recent_date_requested < one_month_ago:
                most_recent_date_requested = one_month_ago

            return TimeStepper.create_from_time(
                self,
                most_recent_date_requested,
                self.configuration.frequency,
                self.configuration.timedelta,
            )

    def handle_response_error(self, response: requests.Response) -> None:
        if not response.ok:
            message = f"Request on Microsoft Graph API failed with status {response.status_code} - {response.text}"
            self.log(message=message, level="error")

            response.raise_for_status()

    def fetch_events(self, start: datetime, end: datetime) -> Generator[list, None, None]:
        self.log(message=f"Querying timerange {start} to {end}.", level="info")

        url = "https://graph.microsoft.com/v1.0/admin/exchange/tracing/messageTraces"
        # NOTE: $orderby won't work here, so we will receive events sorted from the most recent to the oldest
        params: dict[str, Any] | None = {
            "$format": "json",
            "$filter": f"receivedDateTime ge {start.strftime(self.RFC3339_STRICT_FORMAT)} and receivedDateTime le {end.strftime(self.RFC3339_STRICT_FORMAT)}",
            "$top": 1_000,
        }

        # iterate through pages
        while self.running:
            response: requests.Response = self.client.get(url=url, params=params, timeout=60)
            self.handle_response_error(response)

            raw = response.json()

            events = raw.get("value", [])
            if len(events) > 0:
                yield events

            else:
                return

            next_url = raw.get("@odata.nextLink")
            params = None  # to avoid breaking URL with already set URL parameters

            if next_url:
                url = next_url
            else:
                break

    def run(self):  # pragma: no cover
        self.log(message="Office365 MessageTrace Trigger has started.", level="info")

        for start, end in self.stepper.ranges():
            # check if the trigger should stop
            if not self.running:
                break

            try:
                duration_start = time.time()
                for events in self.fetch_events(start, end):
                    batch_of_events = [
                        orjson.dumps(event).decode("utf-8") for event in events if event["id"] not in self.events_cache
                    ]
                    if len(batch_of_events) > 0:
                        self.log(message=f"Forwarding {len(batch_of_events)} records", level="info")
                        self.push_events_to_intakes(events=batch_of_events)
                        OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))

                        # mark sent events as processed
                        for event in events:
                            self.events_cache[event["id"]] = True

                        self.save_events_cache()

                    else:
                        self.log(message="No records to forward", level="info")

                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                    time.time() - duration_start
                )

            except AuthenticationError as e:
                if e.result:
                    self.log(message="Error: {0}".format(e.result.get("error")), level="error")
                    self.log(message="Error description: {0}".format(e.result.get("error_description")), level="error")
                    self.log(message="Correlation ID: {0}".format(e.result.get("correlation_id")), level="error")

                self.log(str(e), level="critical")

            except Exception as ex:
                self.log_exception(ex, message="Failed to fetch events.")
                raise ex

            finally:
                # save in context the most recent date seen
                with self.context as cache:
                    cache["most_recent_date_requested"] = end.isoformat()
