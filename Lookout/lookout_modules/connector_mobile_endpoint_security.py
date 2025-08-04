import json
import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from threading import Event, Thread
from typing import Generator, cast

import orjson
import requests
from dateutil.parser import isoparse
from sekoia_automation.checkpoint import CheckpointCursor
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from . import LookoutModule
from .client import ApiClient
from .client.server_sent_event import SSEvent
from .client.sse_client import SSEClient
from .logger import get_logger
from .metrics import EVENTS_LAG, OUTCOMING_EVENTS

logger = get_logger()


class ShutdownException(Exception):
    pass


class AuthorizationError(Exception):
    pass


class MobileEndpointSecurityConnectorConfiguration(DefaultConnectorConfiguration):
    pass


class MobileEndpointSecurityThread(Thread):
    YIELD_EVENTS = ["events", "heartbeat"]
    RECONNECT_EVENTS = ["end", "reconnect"]

    def __init__(self, connector: "MobileEndpointSecurityConnector") -> None:
        super().__init__()

        self.connector = connector
        self.retry_ms = cast(int, None)

        self.cursor = CheckpointCursor(path=self.connector.data_path)
        self.last_event_id = self.cursor.offset

        self._stop_event = Event()

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def running(self) -> bool:
        return not self._stop_event.is_set()

    def log(self, *args, **kwargs):
        self.connector.log(*args, **kwargs)

    def log_exception(self, *args, **kwargs):
        self.connector.log_exception(*args, **kwargs)

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            base_url=self.connector.module.configuration.base_url,
            api_token=self.connector.module.configuration.api_token,
        )

    def get_sse_stream(self, params: dict | None = None, timeout: float = 60) -> requests.Response:
        headers = {"Accept": "text/event-stream", "Cache-Control": "no-cache"}
        base_url = self.connector.module.configuration.base_url

        try:
            response = self.client.get(
                f"{base_url}/mra/stream/v2/events", stream=True, headers=headers, params=params, timeout=timeout
            )
            response.raise_for_status()

            return response

        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 401:
                self.log("Unauthorized error", level="critical")

                try:
                    raw = err.response.json()
                    error = raw["error"]
                    error_description = raw["error_description"]
                    logger.error("Unauthorized error", error=error, error_description=error_description)

                except Exception:
                    pass

            raise

    def fetch_events(self) -> Generator[SSEvent, None, None]:
        if self.last_event_id:
            params = {"last_id": self.last_event_id}

        else:
            # the very first run - start from an hour ago
            start_time = datetime.now(timezone.utc) - timedelta(hours=1)
            params = {"start_time": start_time.isoformat()}

        stream = self.get_sse_stream(params=params, timeout=60)
        sse_client = SSEClient(stream)

        for ss_event in sse_client.iter_stream_events():
            if not self.running:
                break

            if ss_event.id:
                self.last_event_id = ss_event.id

            if ss_event.event in self.YIELD_EVENTS:
                yield ss_event

            elif ss_event.event in self.RECONNECT_EVENTS:
                if ss_event.retry:
                    self.retry_ms = ss_event.retry

                self.log(f"{ss_event.event} event received, shutting down...", level="info")
                if self.retry_ms:
                    wait_time_seconds = round(self.retry_ms / 1000.0, 2)
                    self.log("Waiting %d seconds before reconnect" % wait_time_seconds)

                    time.sleep(wait_time_seconds)

                break

        # shutdown
        sse_client.close()

    def run(self) -> None:
        while self.running:
            for event in self.fetch_events():
                if event.event == "events":
                    mra_events = []
                    try:
                        mra_events = json.loads(event.data).get("events", [])

                    except ValueError as e:
                        self.log_exception(exception=e, message="failed to parse mra events from sse client")

                    if len(mra_events) > 0:
                        most_recent_date_seen = max(isoparse(item["created_time"]) for item in mra_events)
                        batch_of_events = [orjson.dumps(event).decode("utf-8") for event in mra_events]

                        self.log(
                            message=f"Forwarded {len(batch_of_events)} events to the intake",
                            level="info",
                        )
                        OUTCOMING_EVENTS.labels(intake_key=self.connector.configuration.intake_key).inc(
                            len(batch_of_events)
                        )
                        self.connector.push_events_to_intakes(events=batch_of_events)

                        # save last seen event id
                        self.cursor.offset = self.last_event_id

                        now = datetime.now(timezone.utc)
                        current_lag = now - most_recent_date_seen
                        EVENTS_LAG.labels(intake_key=self.connector.configuration.intake_key).set(
                            current_lag.total_seconds()
                        )

                elif event.event == "heartbeat":
                    logger.debug("Received heartbeat")
                    EVENTS_LAG.labels(intake_key=self.connector.configuration.intake_key).set(0)


class MobileEndpointSecurityConnector(Connector):
    module: LookoutModule
    configuration: MobileEndpointSecurityConnectorConfiguration

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def run(self) -> None:
        self.log("Starting collecting Lookout MES events", level="info")

        worker = MobileEndpointSecurityThread(connector=self)

        try:
            worker.start()

            while self.running:
                if worker.running and not worker.is_alive():
                    self.log("Restarting thread", level="info")
                    worker = MobileEndpointSecurityThread(connector=self)
                    worker.start()

                self.log("Waiting for events", level="info")
                time.sleep(60)

            worker.stop()
            worker.join()

        except KeyboardInterrupt:
            worker.stop()
            worker.join()
