import time
from datetime import datetime, timedelta, timezone

from functools import cached_property
import orjson
from typing import Optional, Dict, Any, Tuple, List

from requests.exceptions import HTTPError
from urllib3.exceptions import HTTPError as BaseHTTPError
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from cortex_module.helper import handle_fqdn
from cortex_module.base import CortexConnector
from cortex_module.client import ApiClient
from cortex_module.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


class CortexEDRConfiguration(DefaultConnectorConfiguration):
    chunk_size: int = 100
    frequency: int = 60


class CortexQueryEDRTrigger(CortexConnector):
    """
    Cortex EDR Query reads the alerts messages exposed after quering the Cortex
    API and forward it to the playbook run.
    """

    configuration: CortexEDRConfiguration

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.query: Dict[str, Any] = {
            "request_data": {
                "filters": [{"field": "creation_time", "operator": "gte", "value": 0}],
                "search_from": 0,
                "search_to": 0,
                "sort": {"field": "creation_time", "keyword": "desc"},
            }
        }
        self._timestamp_cursor = 0

    @property
    def timestamp_cursor(self) -> int:
        now = datetime.now(timezone.utc)

        with self.context as cache:
            timestamp_cursor = cache.get("timestamp_cursor")

            if timestamp_cursor is None:
                before_five_minutes = now - timedelta(minutes=5)
                return int(before_five_minutes.timestamp())

            # We don't collect events older than 7 days
            one_week_ago = int((now - timedelta(days=7)).timestamp()) * 1000
            if timestamp_cursor < one_week_ago:
                timestamp_cursor = one_week_ago

            return int(timestamp_cursor)

    @timestamp_cursor.setter
    def timestamp_cursor(self, time: int) -> None:
        # add 1 second to the most recent date seen
        self._timestamp_cursor = time + 1000
        with self.context as cache:
            cache["timestamp_cursor"] = self._timestamp_cursor

    @cached_property
    def alert_url(self) -> str:
        return handle_fqdn(self.module.configuration.fqdn)

    @cached_property
    def pagination_limit(self) -> int:
        return max(self.configuration.chunk_size, 100)

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            self.module.configuration.api_key,
            self.module.configuration.api_key_id,
        )

    def split_alerts_events(self, alerts: List[Any]) -> List[str]:
        """Split events from alerts and put them in the same list"""

        combined_data = []
        for alert in alerts:
            shared_id = alert.get("alert_id")
            events = alert.get("events")
            del alert["events"]
            combined_data.append(orjson.dumps(alert).decode("utf-8"))
            for event in events:
                event["alert_id"] = shared_id
                combined_data.append(orjson.dumps(event).decode("utf-8"))

        return combined_data

    def get_alerts_events_by_offset(self, offset: int, creation_time: int, pagination: int) -> Tuple[int, List[Any]]:
        """Requests the Cortex API using the offset"""

        search_from, serch_to = offset, offset + pagination
        self.query["request_data"]["search_from"] = search_from
        self.query["request_data"]["search_to"] = serch_to
        self.query["request_data"]["filters"][0]["value"] = creation_time

        # Get the alerts
        response = self.client.post(url=self.alert_url, json=self.query)
        response.raise_for_status()

        # Extract the payload
        response_query = response.json().get("reply", {})

        # extract alerts
        alerts = response_query.get("alerts") or []
        combined_data = self.split_alerts_events(alerts)

        return response_query["total_count"], combined_data

    def get_all_alerts(self, pagination: int) -> None:
        """Get all Cortex alerts from the API"""

        has_more_events = True
        page_number = 0
        events = []

        while has_more_events:
            total_alerts, combined_data = self.get_alerts_events_by_offset(
                page_number * pagination, self.timestamp_cursor, pagination
            )
            self.log(message=f"Sending batch of {len(combined_data)} events", level="info")
            has_more_events = total_alerts > (page_number + 1) * pagination
            page_number += 1
            events.extend(combined_data)

            # Not push empty data
            if len(combined_data) > 0:
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(combined_data))
                self.push_events_to_intakes(events=combined_data)

        current_lag: int = 0
        if len(events) > 0:
            most_recent_timestamp = orjson.loads(events[0]).get("detection_timestamp")
            self.timestamp_cursor = most_recent_timestamp

            # compute the current_lag in seconds
            current_lag = int(time.time() - (most_recent_timestamp / 1000))

        else:
            self.log(message=f"No alerts to forward at {self.timestamp_cursor}", level="info")

        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)

    def forward_next_batch(self) -> None:
        """
        Collect and forward the next batch of alerts
        """
        start = time.time()
        try:
            self.get_all_alerts(self.pagination_limit)

        except (HTTPError, BaseHTTPError) as ex:
            error_response = getattr(ex, "response", None)
            if error_response is None:
                self.log_exception(ex, message="Response does not contain any valid data")
            else:
                http_status_code = error_response.status_code

                if http_status_code == 401:
                    self.log(level="critical", message="Authentication failed: Credentials are invalid")
                elif http_status_code == 403:
                    self.log(
                        level="critical",
                        message="Permission denied: The operation isn't allowed for these credentials",
                    )
                else:
                    self.log_exception(ex, message="Failed to get next batch of events")
        except Exception as ex:
            self.log_exception(ex, message="An unknown exception occurred")
            raise

        duration = int(time.time() - start)
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(duration)

        delta_sleep = self.configuration.frequency - duration
        if delta_sleep > 0:
            time.sleep(delta_sleep)

    def run(self) -> None:
        """Run Cortex EDR Connector"""

        self.log(message="Cortex EDR Events Trigger has started", level="info")
        try:
            while self.running:
                self.forward_next_batch()
        finally:
            self.log(message="Cortex Events Trigger has stopped", level="info")
