import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Any, Dict, List, Optional, Tuple

import orjson
from cachetools import Cache, LRUCache
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON
from urllib3.exceptions import HTTPError as BaseHTTPError

from cortex_module.base import CortexConnector
from cortex_module.client import ApiClient
from cortex_module.helper import handle_issues_fqdn
from cortex_module.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


class CortexXDRIssuesConfiguration(DefaultConnectorConfiguration):
    chunk_size: int = 100
    frequency: int = 60


class CortexQueryXDRIssuesTrigger(CortexConnector):
    """
    Cortex XDR Query reads issues exposed after querying the Cortex
    API and forwards them to the playbook run.
    """

    configuration: CortexXDRIssuesConfiguration

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context_issues.json", self._data_path)
        self.query: Dict[str, Any] = {
            "request_data": {
                "filters": [{"field": "modification_time", "operator": "gte", "value": 0}],
                "search_from": 0,
                "search_to": 0,
                "sort": {"field": "modification_time", "keyword": "desc"},
            }
        }
        self._timestamp_cursor = 0

        self.cache_size = 10_000
        self.issues_cache: Cache[str, bool] = self.load_issues_cache()
        self._connection_issue_detected = False

    def load_issues_cache(self) -> Cache[str, bool]:
        result: LRUCache[str, bool] = LRUCache(maxsize=self.cache_size)

        with self.context as cache:
            issue_ids = cache.get("issues", [])

        for issue_id in issue_ids:
            result[issue_id] = True

        return result

    def save_issues_cache(self) -> None:
        with self.context as cache:
            cache["issues"] = list(self.issues_cache.keys())

    @property
    def timestamp_cursor(self) -> int:
        now = datetime.now(timezone.utc)

        with self.context as cache:
            timestamp_cursor = cache.get("timestamp_cursor")

            if timestamp_cursor is None:
                before_five_minutes = now - timedelta(minutes=5)
                return int(before_five_minutes.timestamp() * 1000)

            one_week_ago = int((now - timedelta(days=7)).timestamp()) * 1000
            if timestamp_cursor < one_week_ago:
                timestamp_cursor = one_week_ago

            return int(timestamp_cursor)

    @timestamp_cursor.setter
    def timestamp_cursor(self, time: int) -> None:
        self._timestamp_cursor = time
        with self.context as cache:
            cache["timestamp_cursor"] = self._timestamp_cursor

    @cached_property
    def issue_url(self) -> str:
        return handle_issues_fqdn(self.module.configuration.fqdn)

    @cached_property
    def pagination_limit(self) -> int:
        return max(self.configuration.chunk_size, 100)

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            self.module.configuration.api_key,
            self.module.configuration.api_key_id,
        )

    def normalize_issues(self, issues: List[Any]) -> List[str]:
        normalized_data: List[str] = []
        for issue in issues:
            issue_id = issue.get("issue_id")
            if issue_id is None:
                self.log(level="warning", message="Skipping Cortex issue without issue_id")
                continue

            normalized_issue_id = f"{issue_id}:{issue.get('modification_time')}"
            if normalized_issue_id in self.issues_cache:
                continue

            self.issues_cache[normalized_issue_id] = True
            normalized_data.append(orjson.dumps(issue).decode("utf-8"))

        return normalized_data

    def get_issues_by_offset(self, offset: int, modification_time: int, pagination: int) -> Tuple[int, List[Any]]:
        search_from, search_to = offset, offset + pagination
        self.query["request_data"]["search_from"] = search_from
        self.query["request_data"]["search_to"] = search_to
        self.query["request_data"]["filters"][0]["value"] = modification_time

        response = self.client.post(url=self.issue_url, json=self.query)
        response.raise_for_status()

        response_query = response.json().get("reply", {})
        issues = response_query.get("issues") or []
        combined_data = self.normalize_issues(issues)

        return response_query["total_count"], combined_data

    def get_all_issues(self, pagination: int) -> None:
        has_more_events = True
        page_number = 0
        events = []

        while has_more_events:
            total_issues, combined_data = self.get_issues_by_offset(
                page_number * pagination, self.timestamp_cursor, pagination
            )
            self.log(message=f"Sending batch of {len(combined_data)} issues", level="info")
            has_more_events = total_issues > (page_number + 1) * pagination
            page_number += 1
            events.extend(combined_data)

            if len(combined_data) > 0:
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(combined_data))
                self.push_events_to_intakes(events=combined_data)
                self.save_issues_cache()

        current_lag: int = 0
        if len(events) > 0:
            most_recent_timestamp = orjson.loads(events[0]).get("modification_time")
            if most_recent_timestamp is None:
                raise ValueError("Received Cortex issue without modification_time")
            self.timestamp_cursor = most_recent_timestamp
            current_lag = int(time.time() - (most_recent_timestamp / 1000))
        else:
            self.log(message=f"No issues to forward at {self.timestamp_cursor}", level="info")

        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)

    def forward_next_batch(self) -> None:
        """
        Collect and forward the next batch of issues.
        """
        start = time.time()
        connection_issue_detected = self._connection_issue_detected
        try:
            self.get_all_issues(self.pagination_limit)
            if connection_issue_detected:
                self.log(
                    level="info",
                    message="Cortex connection restored, the connector reconnected successfully",
                )
                self._connection_issue_detected = False

        except RequestsConnectionError:
            self._connection_issue_detected = True
            self.log(
                level="warning",
                message="Temporary connection issue while fetching Cortex issues, will retry on next run",
            )
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
                    self.log_exception(ex, message="Failed to get next batch of issues")
        except Exception as ex:
            self.log_exception(ex, message="An unknown exception occurred")
            raise

        duration = int(time.time() - start)
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(duration)

        delta_sleep = self.configuration.frequency - duration
        if delta_sleep > 0:
            time.sleep(delta_sleep)

    def run(self) -> None:
        self.log(message="Cortex XDR Issues Trigger has started", level="info")
        try:
            while self.running:
                self.forward_next_batch()
        finally:
            self.log(message="Cortex XDR Issues Trigger has stopped", level="info")
