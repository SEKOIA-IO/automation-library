import time
from abc import abstractmethod
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Any

import orjson
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from sophos_module.base import SophosConnector
from sophos_module.fusion_queries import TENANT_MARKERS
from sophos_module.helper import latest_timestamp
from sophos_module.logging import get_logger
from sophos_module.metrics import EVENTS_LAG, INCOMING_EVENTS, OUTCOMING_EVENTS

# per-cycle diagnostics go to the pod logs only: the connector logs (self.log) are shown to the user
logger = get_logger()


# the status of a data lake query is polled every 2 seconds, for 5 minutes at most
QUERY_STATUS_POLL_INTERVAL = 2
MAX_QUERY_STATUS_POLLS = 150


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

    name = "Sophos IoC query trigger"
    collect_error_action = "Failed to query the Sophos data lake"

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

    def check_fusion_upgrade(self) -> bool | None:
        """
        Check whether the tenant is upgraded to Sophos Fusion: the XDR Query API then returns no new data.

        The markers come from the GraphQL tenant of Sophos Fusion. Best effort: any failure gives None (unknown).
        """
        self._last_fusion_check = datetime.now(UTC)
        try:
            tenant_id = self.authentication.get_credentials().tenancy_id
            # best effort: one short attempt, so an unreachable GraphQL API never delays the IoC collection
            tenant = self.client.graphql(TENANT_MARKERS, {"id": tenant_id}, best_effort=True).get("tenant") or {}
            markers = tenant["centralTenant"] or {}
        except Exception as error:
            logger.info("Unable to check whether the tenant is upgraded to Sophos Fusion", error=str(error))
            self.fusion_upgraded = None
            return None

        xdr_ownership, hydrate_to = markers.get("xdrOwnership"), markers.get("hydrateTo")
        # read in Loki to validate the markers on tenants not upgraded yet
        logger.info("Sophos Fusion markers of the tenant", xdrOwnership=xdr_ownership, hydrateTo=hydrate_to)

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

    def post_query(self, query: dict[str, Any]) -> tuple[str, str | None]:
        # It's the first step of our query treatment.
        # Posting the query
        logger.info("Querying the Sophos data lake", from_date=self.from_date.isoformat())

        response = self.client.run_query(json_query=query)
        if response.status_code >= 400:
            self.log_http_error("Failed to post the query to the Sophos data lake", response)
            return "failed", None

        result = response.json()

        query_id = result.get("id")

        if query_id is None:
            self.log_error("Failed to post the query to the Sophos data lake: no query id returned")
            logger.error("Query post returned no id", response=str(result)[:1000])
            return "failed", query_id

        result_query_status: dict[str, Any] = {}
        for polls in range(1, MAX_QUERY_STATUS_POLLS + 1):
            # Give time for query to finish.
            time.sleep(QUERY_STATUS_POLL_INTERVAL)
            # It's the Second step of our query treatment.
            # Checking the status of our query.
            response_query_status = self.client.get_query_status(query_id)
            status_code = response_query_status.status_code
            if status_code >= 400:
                self.log_http_error("Failed to get the status of the Sophos data lake query", response_query_status)
                if status_code < 500 and status_code != 429:
                    # client error (unknown or expired query, access refused): polling again would not help
                    return "failed", query_id
                continue

            result_query_status = response_query_status.json()
            if result_query_status.get("status") == "finished":
                break
        else:
            self.log_error(
                "The Sophos data lake query did not finish within "
                f"{MAX_QUERY_STATUS_POLLS * QUERY_STATUS_POLL_INTERVAL // 60} minutes: retried on the next cycle"
            )
            logger.error("Query status polling timed out", query_id=query_id, polls=polls)
            return "failed", query_id

        result = result_query_status.get("result")
        logger.info("Query finished", query_id=query_id, result=result, polls=polls)

        if result != "succeeded":
            details = {
                key: value
                for key, value in result_query_status.items()
                if key.lower().startswith("error") or key in ("message", "details")
            }
            # no query id in the message: identical failures are deduplicated
            self.log_error(f"The Sophos data lake query ended with result {result}: {details}")
            logger.error("Query failed", query_id=query_id, result=result, details=details)

        return result, query_id

    def _observe_items_events_lag(self, items: list[dict[str, Any]]) -> None:
        most_recent_timestamp = latest_timestamp(items, ("calendar_time",))
        if most_recent_timestamp is None:
            # can't measure lag, because there's no parseable timestamp
            return

        events_lag = int(time.time() - most_recent_timestamp)
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(events_lag)

    def getting_results(self, pagination: int) -> None:
        now = datetime.now(UTC)
        forwarded_before = self.events_sum

        result, query_id = self.post_query(self.query)

        if result != "succeeded":
            # the cause is already logged by post_query: the checkpoint is kept and the query retried next cycle
            logger.warning("No IoC collected, checkpoint kept", from_date=self.from_date.isoformat())
        else:
            # If the result succeed ==> get the data.
            response: dict[str, Any] = self.client.get_query_results(query_id, pagination).json()
            items = response.get("items", [])
            self._observe_items_events_lag(items)
            INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(items))

            if len(items) > 0:
                messages = [orjson.dumps(message).decode("utf-8") for message in items]
                next_key = response.get("pages", {}).get("nextKey")
                pages = 1
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
                    pages += 1
                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(next_messages))
                    self.push_events_to_intakes(events=next_messages)
                    self.events_sum += len(next_messages)
                    next_key = response_next_page.get("pages", {}).get("nextKey")

                most_recent_date_seen = now
                self.from_date = most_recent_date_seen
                self.cursor.offset = most_recent_date_seen
                logger.info(
                    "IoCs collected",
                    pages=pages,
                    forwarded=self.events_sum - forwarded_before,
                    checkpoint=most_recent_date_seen.isoformat(),
                )

            else:
                logger.info("No new IoC", from_date=self.from_date.isoformat())
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)
                self.warn_if_stalled()

    def collect(self) -> None:
        self.getting_results(self.pagination_limit)

    def before_collect(self) -> None:
        self.check_fusion_upgrade_daily()


class SophosXDRIOCQuery(SophosXDRQueryTrigger):
    @property
    def query(self) -> dict[str, Any]:
        return {
            "adHocQuery": {"template": "SELECT * FROM xdr_ioc_view WHERE ioc_detection_weight > 3"},
            "from": self.from_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
