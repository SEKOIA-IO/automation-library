import time
from datetime import datetime, timedelta, timezone
from dateutil.parser import isoparse
from functools import cached_property
import orjson

from requests.exceptions import HTTPError
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON
from urllib3.exceptions import HTTPError as BaseHTTPError

from cortex_module.base import CortexConnector
from cortex_module.client import ApiClient
from cortex_module.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_EVENTS, OUTCOMING_EVENTS


class CortexEDRConfiguration(DefaultConnectorConfiguration):
    chunk_size: int = 100
    frequency: int = 60


class CortexQueryEDRTrigger(CortexConnector):
    """
    Cortex EDR Query reads the alerts messages exposed after quering the Cortex
    API and forward it to the playbook run.
    """

    configuration: CortexEDRConfiguration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.query: dict = {
            "request_data": {
                "filters": [{"field": "creation_time", "operator": "gte", "value": 0}],
                "search_from": 0,
                "search_to": 0,
                "sort": {"field": "creation_time", "keyword": "desc"},
            }
        }
        self._timestamp_cursor = None

    @property
    def timestamp_cursor(self):
        now = datetime.now(timezone.utc)

        with self.context as cache:
            timestamp_cursor_str = cache.get("timestamp_cursor")

            if timestamp_cursor_str is None:
                before_two_days = now - timedelta(days=2)
                return int(before_two_days.timestamp())

            timestamp_cursor = int(isoparse(timestamp_cursor_str).timestamp())

            return timestamp_cursor

    @timestamp_cursor.setter
    def timestamp_cursor(self, time) -> None:
        if len(str(time)) == 13:
            time_to_iso8601 = datetime.utcfromtimestamp(time / 1000.0).isoformat()
        else:
            time_to_iso8601 = datetime.utcfromtimestamp(time).isoformat()
        self._timestamp_cursor = time_to_iso8601
        with self.context as cache:
            cache["timestamp_cursor"] = self._timestamp_cursor

    @cached_property
    def alert_url(self) -> str:
        return f"https://api-{self.module.configuration.fqdn}/public_api/v1/alerts/get_alerts_multi_events"

    @cached_property
    def pagination_limit(self) -> int:
        return max(self.configuration.chunk_size, 100)

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            self.module.configuration.api_key,
            self.module.configuration.api_key_id,
        )

    def split_alerts_events(self, alerts: list):
        """Split events from alerts and put them in the same list"""

        combined_data = []
        for alert in alerts:
            shared_id = alert.get("alert_id")
            events = alert.get("events")
            del alert["events"]
            combined_data.append(orjson.dumps(alert).decode("utf-8"))
            for event in events:
                event["external_id"] = shared_id
                combined_data.append(orjson.dumps(event).decode("utf-8"))

        return combined_data

    def get_alerts_events_by_offset(self, offset: int, creation_time: int, pagination: int):
        """Requests the Cortex API using the offset"""

        search_from, serch_to = offset, offset + pagination
        self.query["request_data"]["search_from"] = search_from
        self.query["request_data"]["search_to"] = serch_to
        self.query["request_data"]["filters"][0]["value"] = creation_time

        response_query = self.client.post(url=self.alert_url, json=self.query).json().get("reply")
        combined_data = self.split_alerts_events(response_query.get("alerts"))

        return response_query.get("total_count"), combined_data

    def get_all_alerts(self, pagination: int):
        """Get all Cortex alerts from the API"""

        total_alerts, combined_data = self.get_alerts_events_by_offset(0, self.timestamp_cursor, pagination)

        if total_alerts > 0:
            INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(total_alerts)
            self.log(message=f"Sending batch number 1 of {len(combined_data)} data", level="info")
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(combined_data))
            self.push_events_to_intakes(events=combined_data)

            if total_alerts > pagination:
                count_batch = 2
                offset = pagination
                while total_alerts > offset:
                    total_alerts, new_combined_data = self.get_alerts_events_by_offset(
                        offset, self.timestamp_cursor, pagination
                    )
                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(new_combined_data))
                    self.log(
                        message=f"Sending batch number {count_batch} of {len(new_combined_data)} events", level="info"
                    )
                    combined_data.extend(new_combined_data)
                    offset += pagination
                    count_batch += 1

            most_recent_timestamp = orjson.loads(combined_data[0]).get("detection_timestamp")
            events_lag = int(time.time() - most_recent_timestamp)
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).observe(events_lag)
            self.timestamp_cursor = most_recent_timestamp

        else:
            self.log(message=f"No alerts to forward at {self.timestamp_cursor}", level="info")

    def run(self) -> None:
        """Run Cortex EDR Connector"""

        self.log(message="Cortex EDR Events Trigger has started", level="info")
        try:
            while self.running:
                start = time.time()
                try:
                    self.get_all_alerts(self.pagination_limit)

                except (HTTPError, BaseHTTPError) as ex:
                    self.log_exception(ex, message="Failed to get next batch of events")
                except Exception as ex:
                    self.log_exception(ex, message="An unknown exception occurred")
                    raise

                duration = int(time.time() - start)
                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(duration)

                delta_sleep = self.configuration.frequency - duration
                if delta_sleep > 0:
                    time.sleep(delta_sleep)
        finally:
            self.log(message="Cortex Events Trigger has stopped", level="info")
