import time
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Any

import orjson
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import DefaultConnectorConfiguration

from sophos_module.base import SophosConnector
from sophos_module.client.exceptions import SophosGraphQLError
from sophos_module.fusion_queries import DETECTION_SEARCH
from sophos_module.logging import get_logger
from sophos_module.metrics import EVENTS_LAG, INCOMING_EVENTS, OUTCOMING_EVENTS

# per-cycle diagnostics go to the pod logs only: the connector logs (self.log) are shown to the user
logger = get_logger()

# detectionSearch returns at most 10,000 results per search: larger windows are split
MAX_RESULTS_PER_SEARCH = 10000
# cycles that search an incomplete window again (empty page before the announced total), before moving on
MAX_INCOMPLETE_WINDOW_RETRIES = 3
# error code of a search response without status or results, and without GraphQL errors
INCOMPLETE_RESPONSE = "INCOMPLETE_RESPONSE"


class SophosFusionDetectionsConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    chunk_size: int = 1000
    min_severity: float | None = None


def timestamp_to_rfc3339(value: dict[str, Any]) -> str:
    """Convert a GraphQL Timestamp ({seconds, nanos}) into an RFC 3339 date with milliseconds."""
    dt = datetime.fromtimestamp(int(value["seconds"]), tz=UTC) + timedelta(
        microseconds=int(value.get("nanos") or 0) // 1000
    )
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def is_timestamp(value: Any) -> bool:
    return isinstance(value, dict) and set(value.keys()) == {"seconds", "nanos"}


def clean_detection(value: Any) -> Any:
    """Convert the GraphQL timestamps into dates and drop the null and empty values, recursively."""
    if is_timestamp(value):
        return timestamp_to_rfc3339(value)

    if isinstance(value, dict):
        cleaned_dict = {key: clean_detection(item) for key, item in value.items()}
        return {key: item for key, item in cleaned_dict.items() if item not in (None, {}, [])}

    if isinstance(value, list):
        cleaned_list = [clean_detection(item) for item in value]
        return [item for item in cleaned_list if item not in (None, {}, [])]

    return value


def format_ql_date(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class SophosFusionDetectionsTrigger(SophosConnector):
    """
    Collect the detections of Sophos Fusion (Security Operations) with the Detections GraphQL API.

    Each cycle searches the detections of the window [checkpoint - overlap, now - latency].
    The overlap catches the detections indexed late; the detections already forwarded in the overlap are skipped.
    """

    configuration: SophosFusionDetectionsConfiguration

    name = "Sophos Fusion detections trigger"
    collect_error_action = "Failed to search the Sophos Fusion detections"

    overlap = timedelta(minutes=5)
    latency = timedelta(minutes=1)

    def __init__(self, *args: Any, **kwargs: Any | None) -> None:
        super().__init__(*args, **kwargs)
        self.cursor = CheckpointDatetime(
            path=self.data_path, start_at=timedelta(days=1), ignore_older_than=timedelta(days=30)
        )
        # detection id -> window end at which it was seen, to skip the detections already forwarded
        self._seen: dict[str, datetime] = {}
        # consecutive cycles that kept the checkpoint because the window was incomplete
        self._incomplete_window_retries = 0

    @cached_property
    def page_size(self) -> int:
        return min(max(self.configuration.chunk_size, 1), MAX_RESULTS_PER_SEARCH)

    def build_query(self, start: datetime, end: datetime) -> str:
        filters = ""
        if self.configuration.min_severity is not None:
            filters = f"where severity >= {self.configuration.min_severity} "

        return (
            f"from alert {filters}earliest='{format_ql_date(start)}' latest='{format_ql_date(end)}' "
            "| sort created_at asc"
        )

    def search(self, start: datetime, end: datetime, offset: int) -> dict[str, Any]:
        data = self.client.graphql(
            DETECTION_SEARCH,
            {"in": {"cql_query": self.build_query(start, end), "offset": offset, "limit": self.page_size}},
        )
        # only an explicit OK with its alerts is a complete search: anything else keeps the checkpoint
        response = data.get("detectionSearch")
        if not isinstance(response, dict):
            raise SophosGraphQLError(
                [{"message": "no detectionSearch in the response", "extensions": {"code": INCOMPLETE_RESPONSE}}]
            )
        if response.get("status") != "OK":
            raise SophosGraphQLError(
                [
                    {
                        "message": response.get("reason") or "no search status",
                        "extensions": {"code": response.get("status") or INCOMPLETE_RESPONSE},
                    }
                ]
            )
        if not isinstance(response.get("alerts"), dict):
            raise SophosGraphQLError(
                [{"message": "no alerts in the search response", "extensions": {"code": INCOMPLETE_RESPONSE}}]
            )

        return response

    def fetch_window(self, start: datetime, end: datetime) -> tuple[list[dict[str, Any]], bool]:
        """
        Return the detections of the window, and whether all of them were fetched.

        The window is split when it has too many results for one search.
        """
        response = self.search(start, end, offset=0)
        alerts = response.get("alerts") or {}
        total = alerts.get("total_results") or 0

        if total > MAX_RESULTS_PER_SEARCH:
            if end - start > timedelta(seconds=1):
                middle = start + (end - start) / 2
                logger.info(
                    "Too many detections for one search, splitting the window",
                    total_results=total,
                    start=format_ql_date(start),
                    end=format_ql_date(end),
                )
                first, first_complete = self.fetch_window(start, middle)
                second, second_complete = self.fetch_window(middle, end)
                return first + second, first_complete and second_complete

            # the dates of the queries have a one-second precision: this window cannot be split.
            # Searching it again would return the same results, so the collection moves on
            self.log_error(
                f"More than {MAX_RESULTS_PER_SEARCH} Sophos Fusion detections in one second: "
                f"only the first {MAX_RESULTS_PER_SEARCH} were collected"
            )
            logger.error(
                "Window with too many detections cannot be split, detections missed",
                total_results=total,
                start=format_ql_date(start),
                end=format_ql_date(end),
            )

        detections: list[dict[str, Any]] = list(alerts.get("list") or [])
        while len(detections) < min(total, MAX_RESULTS_PER_SEARCH):
            page = (self.search(start, end, offset=len(detections)).get("alerts") or {}).get("list") or []
            if not page:
                logger.warning(
                    "Sophos returned an empty page before the announced total",
                    fetched=len(detections),
                    total_results=total,
                    start=format_ql_date(start),
                    end=format_ql_date(end),
                )
                return detections, False
            detections.extend(page)

        return detections, True

    def _forget_seen_before(self, limit: datetime) -> None:
        self._seen = {key: seen_at for key, seen_at in self._seen.items() if seen_at >= limit}

    def forward_detections(self, detections: list[dict[str, Any]], window_end: datetime) -> int:
        events: list[str] = []
        most_recent_timestamp: float | None = None
        without_id = 0

        for detection in detections:
            detection_id = detection.get("id")
            if detection_id is None:
                without_id += 1
                continue
            if detection_id in self._seen:
                continue
            self._seen[detection_id] = window_end

            created_at = ((detection.get("metadata") or {}).get("created_at") or {}).get("seconds")
            if created_at is not None and (most_recent_timestamp is None or created_at > most_recent_timestamp):
                most_recent_timestamp = float(created_at)

            events.append(orjson.dumps(clean_detection(detection)).decode("utf-8"))

        if most_recent_timestamp is not None:
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(int(time.time() - most_recent_timestamp))

        if without_id:
            logger.warning("Detections without id skipped", count=without_id)

        if events:
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(events))
            for index in range(0, len(events), self.page_size):
                self.push_events_to_intakes(events=events[index : index + self.page_size])

        return len(events)

    def next_batch(self) -> None:
        end = datetime.now(UTC) - self.latency
        start = self.cursor.offset - self.overlap
        if end <= start:
            logger.debug("Window not open yet", start=format_ql_date(start), end=format_ql_date(end))
            return

        try:
            detections, complete = self.fetch_window(start, end)
        except SophosGraphQLError as error:
            # keep the checkpoint: the same window is searched again on the next cycle.
            # Stable message (no dates): the SDK deduplicates identical logs while the error lasts
            self.log(message=f"Failed to search the Sophos Fusion detections: {error}", level="error")
            logger.error(
                "Detection search failed, checkpoint kept",
                error=str(error),
                codes=error.codes,
                start=format_ql_date(start),
                end=format_ql_date(end),
            )
            return

        INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(detections))
        forwarded = self.forward_detections(detections, end)
        logger.info(
            "Detections collected",
            start=format_ql_date(start),
            end=format_ql_date(end),
            collected=len(detections),
            forwarded=forwarded,
            skipped=len(detections) - forwarded,
        )
        if not detections:
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)

        if not complete:
            if self._incomplete_window_retries < MAX_INCOMPLETE_WINDOW_RETRIES:
                # keep the checkpoint: the window is searched again on the next cycle,
                # the detections already forwarded are skipped
                self._incomplete_window_retries += 1
                logger.warning(
                    "Incomplete window, checkpoint kept",
                    retries=self._incomplete_window_retries,
                    start=format_ql_date(start),
                )
                return

            self.log_error(
                "Sophos returned fewer Sophos Fusion detections than announced: some detections may be missing"
            )
            logger.error(
                "Window still incomplete, checkpoint moved", start=format_ql_date(start), end=format_ql_date(end)
            )

        self._incomplete_window_retries = 0
        self.cursor.offset = end
        self._forget_seen_before(start)

    def collect(self) -> None:
        self.next_batch()
