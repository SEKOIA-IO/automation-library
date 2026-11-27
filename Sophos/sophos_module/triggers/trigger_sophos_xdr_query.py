import time
from abc import abstractmethod
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Any

import orjson
from requests.exceptions import HTTPError
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON
from urllib3.exceptions import HTTPError as BaseHTTPError

from sophos_module.base import SophosConnector
from sophos_module.client import SophosApiClient
from sophos_module.client.auth import SophosApiAuthentication
from sophos_module.client.exceptions import SophosApiAuthenticationError
from sophos_module.fusion_queries import TENANT_MARKERS
from sophos_module.helper import latest_timestamp
from sophos_module.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_EVENTS, OUTCOMING_EVENTS

FUSION_UPGRADE_MESSAGE = (
    "This tenant was probably upgraded to Sophos Fusion: the XDR Query API no longer returns new IoCs. "
    "Use the 'Get Sophos Fusion detections' connector instead."
)


class SophosXDRQueryConfiguration(DefaultConnectorConfiguration):
    chunk_size: int = 1000
    frequency: int = 60


class SophosXDRQueryTrigger(SophosConnector):
    """
    The Sophos XDR Query reads the messages exposed after querying the Sophos Data Lake
    API and forward it to the playbook run.

    Good to know : This is the parent class for all other query classes
    """

    configuration: SophosXDRQueryConfiguration

    def __init__(self, *args: Any, **kwargs: Any | None) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.cursor = CheckpointDatetime(
            path=self.data_path, start_at=timedelta(days=1), ignore_older_than=timedelta(days=30)
        )
        self._from_date: datetime = self.cursor.offset
        self.events_sum = 0
        self._last_stall_warning: datetime | None = None
        # Sophos Fusion upgrade, from the tenant markers: True, False, or None when unknown
        self.fusion_upgraded: bool | None = None
        self._last_fusion_check: datetime | None = None

    @property
    def from_date(self) -> datetime:
        # Enforce 30-day limit on every request
        too_old: datetime = datetime.now(UTC) - self.cursor._ignore_older_than
        if self._from_date < too_old:
            return too_old

        return self._from_date

    @from_date.setter
    def from_date(self, value: datetime) -> None:
        self._from_date = value

    @property
    @abstractmethod
    def query(self) -> dict[str, Any]:
        """Return the Sophos XDR query definition."""
        raise NotImplementedError

    @cached_property
    def pagination_limit(self) -> int:
        return max(self.configuration.chunk_size, 1000)

    @cached_property
    def authentication(self) -> SophosApiAuthentication:
        return SophosApiAuthentication(
            api_host=self.module.configuration.api_host,
            authorization_url=self.module.configuration.oauth2_authorization_url,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
        )

    @cached_property
    def client(self) -> SophosApiClient:
        return SophosApiClient(auth=self.authentication, graphql_api_url=self.module.configuration.graphql_api_url)

    def check_fusion_upgrade(self) -> bool | None:
        """
        Check whether the tenant is upgraded to Sophos Fusion: the XDR Query API then returns no new data.

        The markers come from the GraphQL tenant of Sophos Fusion. Best effort: any failure gives None (unknown).
        """
        self._last_fusion_check = datetime.now(UTC)
        try:
            tenant_id = self.authentication.get_credentials().tenancy_id
            tenant = self.client.graphql(TENANT_MARKERS, {"id": tenant_id}).get("tenant") or {}
            markers = tenant["centralTenant"] or {}
        except Exception as error:
            self.log(message=f"Unable to check whether the tenant is upgraded to Sophos Fusion: {error}", level="info")
            self.fusion_upgraded = None
            return None

        xdr_ownership, hydrate_to = markers.get("xdrOwnership"), markers.get("hydrateTo")
        self.log(
            message=f"Sophos Fusion markers of the tenant: xdrOwnership={xdr_ownership}, hydrateTo={hydrate_to}",
            level="info",
        )

        self.fusion_upgraded = xdr_ownership == "securityOperations" or hydrate_to == "taegis"
        if self.fusion_upgraded:
            self.log(message=FUSION_UPGRADE_MESSAGE, level="error")

        return self.fusion_upgraded

    def check_fusion_upgrade_daily(self) -> None:
        """Check the Sophos Fusion markers at startup, then once a day: a tenant can be upgraded at any time."""
        if self._last_fusion_check is None or datetime.now(UTC) - self._last_fusion_check >= timedelta(days=1):
            self.check_fusion_upgrade()

    def warn_if_stalled(self) -> None:
        """
        Fallback when the Sophos Fusion markers are unavailable: warn, at most once a day,
        when nothing was collected for the maximum lookback period.

        No warning when the markers answered: an upgraded tenant is already reported by the daily check,
        and a tenant not upgraded with no IoC for 30 days is legitimate.
        """
        if self.fusion_upgraded is not None:
            return

        now = datetime.now(UTC)
        too_old = now - self.cursor._ignore_older_than
        if self._from_date > too_old:
            return

        if self._last_stall_warning is not None and now - self._last_stall_warning < timedelta(days=1):
            return

        self._last_stall_warning = now
        self.log(
            message=f"No IoC collected for more than {self.cursor._ignore_older_than.days} days. "
            "If the Sophos console shows 'Security Operations' instead of 'Threat Analysis Center', the tenant was "
            "upgraded to Sophos Fusion: use the 'Get Sophos Fusion detections' connector instead.",
            level="warning",
        )

    def run(self) -> None:
        self.log(message="Sophos Events Trigger has started", level="info")

        try:
            # Authenticate with the Sophos API
            self.authentication.get_credentials()

            while self.running:
                start = time.time()
                self.check_fusion_upgrade_daily()
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

        except SophosApiAuthenticationError as ex:
            # Log a critical message, that will stop the connector, when the authentication fails
            self.log(message=str(ex), level="critical")

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
                message=f"Failed to post the query. Status code: {response.status_code}, response: {response.text}"
                f"{self._query_error_hint(response.status_code)}",
                level="error",
            )

            return "failed", None

        result = response.json()

        query_id = result.get("id")

        if query_id is None:
            self.log(message=f"Failed to post the query: no query id in the response {result}", level="error")
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

        if result != "succeeded":
            details = {
                key: value
                for key, value in result_query_status.items()
                if key.lower().startswith("error") or key in ("message", "details")
            }
            self.log(message=f"The query {query_id} ended with result {result}: {details}", level="error")

        return result, query_id

    @staticmethod
    def _query_error_hint(status_code: int) -> str:
        if status_code == 403:
            return (
                ". Check that the API credential has the 'Service Principal Forensics' role"
                " and that the XDR licence of the tenant is valid"
            )
        return ""

    def _observe_items_events_lag(self, items: list[dict[str, Any]]) -> None:
        most_recent_timestamp = latest_timestamp(items, ("calendar_time",))
        if most_recent_timestamp is None:
            # can't measure lag, because there's no parseable timestamp
            return

        events_lag = int(time.time() - most_recent_timestamp)
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(events_lag)

    def getting_results(self, pagination: int) -> None:
        now = datetime.now(UTC)

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
                self.cursor.offset = most_recent_date_seen

            else:
                self.log(message="No messages to forward", level="info")
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)
                self.warn_if_stalled()


class SophosXDRIOCQuery(SophosXDRQueryTrigger):
    @property
    def query(self) -> dict[str, Any]:
        return {
            "adHocQuery": {"template": "SELECT * FROM xdr_ioc_view WHERE ioc_detection_weight > 3"},
            "from": self.from_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
