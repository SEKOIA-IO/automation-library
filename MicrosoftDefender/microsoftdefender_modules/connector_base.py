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

from . import MicrosoftDefenderModule
from .client import GraphApiClient
from .client.auth import AuthenticationError
from .logging import get_logger
from .metrics import FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS
from .timestepper import TimeStepper

logger = get_logger(__name__)


class BaseGraphAPIConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    timedelta: int = 5
    start_time: int = 1


class BaseMicrosoftDefenderGraphAPIConnector(Connector):
    """Base connector for fetching security events from Microsoft Graph API.

    Subclasses must set `endpoint_url`. Override `extra_query_params` to add
    request-specific OData params (e.g. `$expand=alerts`) and `process_events`
    to apply per-resource flattening or dedup logic.
    """

    module: MicrosoftDefenderModule
    configuration: BaseGraphAPIConfiguration

    RFC3339_STRICT_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

    endpoint_url: str = ""
    timestamp_field: str = "createdDateTime"
    id_field: str = "id"
    context_cursor_key: str = "most_recent_date_requested"
    events_cache_context_key: str = "events_cache"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.scopes: list = ["https://graph.microsoft.com/.default"]
        self.context = PersistentJSON("context.json", self.data_path)

        self.cache_size = 2000
        self.events_cache: Cache[str, bool] = self.load_events_cache()

    def load_events_cache(self) -> Cache[str, bool]:
        cache: Cache[str, bool] = LRUCache(maxsize=self.cache_size)

        with self.context as context:
            events_cache = context.get(self.events_cache_context_key, [])

        for uid in events_cache:
            cache[uid] = True

        return cache

    def save_events_cache(self) -> None:
        with self.context as context:
            context[self.events_cache_context_key] = list(self.events_cache.keys())

    @cached_property
    def client(self) -> GraphApiClient:
        return GraphApiClient(
            tenant_id=self.module.configuration.tenant_id,
            client_id=self.module.configuration.app_id,
            client_secret=self.module.configuration.app_secret,
            scopes=self.scopes,
        )

    @cached_property
    def stepper(self) -> TimeStepper:
        with self.context as cache:
            most_recent_date_requested_str = cache.get(self.context_cursor_key)

            if most_recent_date_requested_str is None:
                return TimeStepper.create(
                    self,
                    self.configuration.frequency,
                    self.configuration.timedelta,
                    self.configuration.start_time,
                )

            most_recent_date_requested = isoparse(most_recent_date_requested_str)

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

            try:
                response_json = response.json()

                logger.error(
                    message,
                    error=response_json.get("error"),
                    error_description=response_json.get("error_description"),
                    correlation_id=response_json.get("correlation_id"),
                )

            except requests.exceptions.JSONDecodeError:
                pass

            response.raise_for_status()

    def extra_query_params(self) -> dict[str, Any]:
        """Override to add resource-specific OData query parameters."""
        return {}

    def build_query_params(self, start: datetime, end: datetime) -> dict[str, Any]:
        params: dict[str, Any] = {
            "$format": "json",
            "$orderby": f"{self.timestamp_field} asc",
            "$filter": (
                f"{self.timestamp_field} gt {start.strftime(self.RFC3339_STRICT_FORMAT)}"
                f" and {self.timestamp_field} le {end.strftime(self.RFC3339_STRICT_FORMAT)}"
            ),
            "$top": 1000,
        }
        params.update(self.extra_query_params())
        return params

    def fetch_events(self, start: datetime, end: datetime) -> Generator[list, None, None]:
        self.log(message=f"Querying timerange {start} to {end}.", level="info")

        url = self.endpoint_url
        # Note: even with `gt` we can get the same event for very specific time twice. Thus, we're using cache.
        params: dict[str, Any] | None = self.build_query_params(start, end)

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

    def process_events(self, batch: list[dict]) -> Generator[dict, None, None]:
        """Default: yield events not already in the cache, untouched."""
        for event in batch:
            event_id = event.get(self.id_field)
            if event_id is None or event_id in self.events_cache:
                continue
            yield event

    def run(self):  # pragma: no cover
        self.log(message=f"{self.__class__.__name__} has started.", level="info")

        for start, end in self.stepper.ranges():
            # check if the trigger should stop
            if not self.running:
                break

            try:
                duration_start = time.time()
                for events in self.fetch_events(start, end):
                    batch_of_events = [event for event in self.process_events(events)]

                    if len(batch_of_events) > 0:
                        self.log(message=f"Forwarding {len(batch_of_events)} records", level="info")

                        batch_of_events = [orjson.dumps(event).decode("utf-8") for event in batch_of_events]
                        self.push_events_to_intakes(events=batch_of_events)
                        OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))

                        # mark sent events as processed
                        for event in events:
                            event_id = event.get(self.id_field)
                            if event_id is not None:
                                self.events_cache[event_id] = True

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
                    cache[self.context_cursor_key] = end.isoformat()
