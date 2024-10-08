import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Any, Optional

import orjson
from dateutil.parser import isoparse
from requests.exceptions import HTTPError
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON
from urllib3.exceptions import HTTPError as BaseHTTPError

from sophos_module.base import SophosConnector
from sophos_module.client import SophosApiClient
from sophos_module.client.auth import SophosApiAuthentication
from sophos_module.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_EVENTS, OUTCOMING_EVENTS


class SophosXDRQueryConfiguration(DefaultConnectorConfiguration):
    chunk_size: int = 1000
    frequency: int = 60


class SophosXDRQueryTrigger(SophosConnector):
    """
    The Sophos XDR Qyery reads the messages exposed after quering the Sophos Data Lake
    API and forward it to the playbook run.

    Good to know : This's the parent class for all other query classes
    """

    configuration: SophosXDRQueryConfiguration

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.query: dict[str, Any] = {}
        self.from_date = self.most_recent_date_seen
        self.events_sum = 0

    @property
    def most_recent_date_seen(self) -> datetime:
        now = datetime.now(timezone.utc)

        with self.context as cache:
            most_recent_date_seen_str = cache.get("most_recent_date_seen")

            # if undefined, retrieve events from the last minute
            if most_recent_date_seen_str is None:
                return now - timedelta(days=1)

            # parse the most recent date seen
            most_recent_date_seen = isoparse(most_recent_date_seen_str)

            # We don't retrieve messages older than 1 month according to documentation
            # https://developer.sophos.com/reference/edr/Querying-the-Data-Lake
            one_month_ago = now - timedelta(days=30)
            if most_recent_date_seen < one_month_ago:
                most_recent_date_seen = one_month_ago

            return most_recent_date_seen

    @cached_property
    def pagination_limit(self) -> int:
        return max(self.configuration.chunk_size, 1000)

    @cached_property
    def client(self) -> SophosApiClient:
        auth = SophosApiAuthentication(
            api_host=self.module.configuration.api_host,
            authorization_url=self.module.configuration.oauth2_authorization_url,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
        )

        return SophosApiClient(auth=auth)

    def run(self) -> None:  # pragma: no cover
        self.log(message="Sophos Events Trigger has started", level="info")

        try:
            while self.running:
                start = time.time()
                try:
                    self.getting_results(self.pagination_limit)

                except (HTTPError, BaseHTTPError) as ex:
                    self.log_exception(ex, message="Failed to get next batch of events")
                except Exception as ex:
                    self.log_exception(ex, message="An unknown exception occurred")
                    raise

                # compute the duration of the last events fetching
                duration = int(time.time() - start)
                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(duration)

                # Compute the remaining sleeping time
                delta_sleep = self.configuration.frequency - duration
                # if greater than 0, sleep
                if delta_sleep > 0:
                    time.sleep(delta_sleep)
        finally:
            self.log(message="Sophos Events Trigger has stopped", level="info")

    def post_query(self, query: dict[str, Any]) -> tuple[str, str | None]:
        # It's the first step of our query treatment.
        # Posting the query
        self.log(
            message=f"Querying the Sophos data lake at {self.from_date.strftime('%Y-%m-%d %H:%M:%S')}", level="info"
        )

        response = self.client.run_query(json_query=query)
        if response.status_code >= 400:
            self.log(
                message=f"Failed to post the query. Status code: {response.status_code}, response: {response.text}",
                level="error",
            )

            return "failed", None

        result = response.json()

        query_id = result.get("id")

        if query_id is None:
            return "failed", query_id

        status = ""
        self.log(message=f"Waiting the query {query_id} to complete", level="info")
        while status != "finished":
            # Give time for query to finish.
            time.sleep(2)
            # It's the Second step of our query treatment.
            # Checking the status of our query.
            response_query_status = self.client.get_query_status(query_id)
            if response_query_status.status_code >= 400:
                self.log(
                    message=f"Failed to get the query status. Status code: {response_query_status.status_code}, "
                    f"response: {response_query_status.text}",
                    level="error",
                )

            result_query_status = response_query_status.json()
            status = result_query_status.get("status")
            result = result_query_status.get("result")

        self.log(message=f"Finishing the loop with status {status} and result {result}", level="info")

        return result, query_id

    def _observe_items_events_lag(self, items: list[dict[str, Any]]) -> None:
        def _extract_timestamp(item: dict[str, Any]) -> float:
            RFC3339_STRICT_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
            return datetime.strptime(item["calendar_time"], RFC3339_STRICT_FORMAT).timestamp()

        if len(items) == 0:
            return

        if "calendar_time" not in items[0]:
            # can't measure lag, because there's no timestamp
            return

        most_recent_item: dict[str, Any] = max(items, key=lambda item: item["calendar_time"])  # type: ignore
        most_recent_timestamp = _extract_timestamp(most_recent_item)

        events_lag = int(time.time() - most_recent_timestamp)
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(events_lag)

    def getting_results(self, pagination: int) -> None:
        now = datetime.now(timezone.utc)

        result, query_id = self.post_query(self.query)

        if result != "succeeded":
            self.log(
                message=f"The query failed. No events collected at {self.from_date.strftime('%Y-%m-%d %H:%M:%S')} !!"
            )
        else:
            # If the result succeed ==> get the data.
            response: dict[str, Any] = self.client.get_query_results(query_id, pagination).json()
            items = response.get("items", [])
            self._observe_items_events_lag(items)
            self.log(message=f"Getting results with {len(items)} elements", level="info")
            INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(items))

            if len(items) > 0:
                messages = [orjson.dumps(message).decode("utf-8") for message in items]
                next_key = response.get("pages", {}).get("nextKey")
                self.log(message=f"Sending the first batch of {len(messages)} messages", level="info")
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(messages))
                self.push_events_to_intakes(events=messages)
                self.events_sum += len(messages)

                while next_key:
                    response_next_page: dict[str, Any] = self.client.get_query_results(
                        query_id, pagination, next_key
                    ).json()

                    next_page_items = response_next_page.get("items", [])
                    next_messages = [orjson.dumps(message).decode("utf-8") for message in next_page_items]
                    self._observe_items_events_lag(next_page_items)
                    self.log(message=f"Sending other batches of {len(next_messages)} messages", level="info")
                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(next_messages))
                    self.push_events_to_intakes(events=next_messages)
                    self.events_sum += len(next_messages)
                    next_key = response_next_page.get("pages", {}).get("nextKey")

                most_recent_date_seen = now
                self.from_date = most_recent_date_seen
                with self.context as cache:
                    cache["most_recent_date_seen"] = most_recent_date_seen.strftime("%Y-%m-%dT%H:%M:%SZ")

            else:
                self.log(message="No messages to forward", level="info")
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)


class SophosXDRIOCQuery(SophosXDRQueryTrigger):
    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        super().__init__(*args, **kwargs)

        self.query = {
            "adHocQuery": {"template": "SELECT * FROM xdr_ioc_view WHERE ioc_detection_weight > 3"},
            "from": self.from_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
