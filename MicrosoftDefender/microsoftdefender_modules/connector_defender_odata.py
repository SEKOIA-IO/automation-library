import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Any, Generator

import orjson
import requests
from dateutil.parser import isoparse
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import MicrosoftDefenderModule
from .client import ApiClient
from .logging import get_logger
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS

logger = get_logger(__name__)

RFC3339_STRICT_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


class MicrosoftDefenderODataConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    start_time: int = 1
    base_url: str | None = None


class MicrosoftDefenderODataConnector(Connector):
    """
    Base connector for Defender legacy OData endpoints (alerts, incidents).

    Subclasses declare `endpoint_path` ("/api/alerts" or "/api/incidents").
    Both endpoints share the same incremental-collection shape:
    `$filter=lastUpdateTime gt <iso>` with paging via `@odata.nextLink`.
    """

    module: MicrosoftDefenderModule
    configuration: MicrosoftDefenderODataConnectorConfiguration

    endpoint_path: str = ""
    timestamp_field: str = "lastUpdateTime"
    checkpoint_key: str = "most_recent_update_time"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self.data_path)

    @cached_property
    def base_url(self) -> str:
        url = self.configuration.base_url or self.module.configuration.base_url
        return url.rstrip("/")

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            app_id=self.module.configuration.app_id,
            app_secret=self.module.configuration.app_secret,
            tenant_id=self.module.configuration.tenant_id,
            base_url=self.base_url,
        )

    def _load_checkpoint(self) -> datetime:
        now = datetime.now(timezone.utc)
        one_month_ago = now - timedelta(days=30)

        with self.context as cache:
            cursor = cache.get(self.checkpoint_key)

        if cursor:
            dt = isoparse(cursor)
        else:
            start_hours = self.configuration.start_time or 1
            dt = now - timedelta(hours=start_hours)

        if dt < one_month_ago:
            dt = one_month_ago

        return dt

    def _save_checkpoint(self, dt: datetime) -> None:
        with self.context as cache:
            cache[self.checkpoint_key] = dt.isoformat()

    def _handle_response_error(self, response: requests.Response) -> None:
        if not response.ok:
            message = f"Request on Microsoft Defender API failed with status {response.status_code} - {response.text}"
            self.log(message=message, level="error")
            response.raise_for_status()

    def fetch_events(self, start: datetime) -> Generator[list, None, None]:
        url = f"{self.base_url}{self.endpoint_path}"
        params: dict[str, Any] | None = {
            "$filter": f"{self.timestamp_field} gt {start.strftime(RFC3339_STRICT_FORMAT)}",
            "$orderby": f"{self.timestamp_field} asc",
        }

        while self.running:
            response = self.client.get(url=url, params=params, timeout=60)
            self._handle_response_error(response)

            raw = response.json()
            events = raw.get("value", [])
            if events:
                yield events
            else:
                return

            next_url = raw.get("@odata.nextLink")
            params = None
            if not next_url:
                break
            url = next_url

    def _latest_update(self, events: list[dict], current: datetime) -> datetime:
        latest = current
        for event in events:
            ts = event.get(self.timestamp_field)
            if not ts:
                continue
            try:
                dt = isoparse(ts)
            except (ValueError, TypeError):
                continue
            if dt > latest:
                latest = dt
        return latest

    def run(self) -> None:  # pragma: no cover
        self.log(message=f"{self.__class__.__name__} has started.", level="info")

        while self.running:
            start = self._load_checkpoint()
            most_recent = start
            duration_start = time.time()

            try:
                for events in self.fetch_events(start):
                    most_recent = self._latest_update(events, most_recent)

                    batch = [orjson.dumps(event).decode("utf-8") for event in events]
                    self.log(message=f"Forwarding {len(batch)} records", level="info")
                    self.push_events_to_intakes(events=batch)
                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch))

                if most_recent > start:
                    self._save_checkpoint(most_recent)

                now = datetime.now(timezone.utc)
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(
                    int((now - most_recent).total_seconds())
                )
                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                    time.time() - duration_start
                )

            except Exception as ex:
                self.log_exception(ex, message="Failed to fetch events.")

            time.sleep(self.configuration.frequency)


class MicrosoftDefenderAlertsConnector(MicrosoftDefenderODataConnector):
    """Fetch alerts from the Defender for Endpoint API: {base_url}/api/alerts."""

    endpoint_path = "/api/alerts"
    checkpoint_key = "most_recent_update_time_alerts"


class MicrosoftDefenderIncidentsConnector(MicrosoftDefenderODataConnector):
    """Fetch incidents from the Defender XDR API: {base_url}/api/incidents."""

    endpoint_path = "/api/incidents"
    checkpoint_key = "most_recent_update_time_incidents"
