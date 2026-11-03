import base64
import hashlib
import os
import re
import time
import urllib.parse
from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Any, Generator, cast

import orjson
import requests
from cachetools import Cache, LRUCache
from pydantic.v1 import Field
from sekoia_automation.checkpoint import CheckpointTimestamp, TimeUnit
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from . import AkamaiModule
from .client import ApiClient
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class AkamaiWAFLogsConnectorConfiguration(DefaultConnectorConfiguration):
    config_id: str = Field(..., description="The Web Security Configuration ID")
    frequency: int = Field(60, description="Batch frequency in seconds", ge=1)


class AkamaiWAFLogsConnector(Connector):
    module: AkamaiModule
    configuration: AkamaiWAFLogsConnectorConfiguration

    def __init__(self, *args, **kwargs) -> None:
        """Initialize connector state, cache, and batch sizing."""
        super().__init__(*args, **kwargs)

        self.cursor = CheckpointTimestamp(
            path=self._data_path,
            time_unit=TimeUnit.SECOND,
            start_at=timedelta(hours=1),
            ignore_older_than=timedelta(hours=12),
        )
        self.from_timestamp: int = self.cursor.offset

        # This cache should be big enough to cover all events within 1 second.
        self.cache_size = 10_000
        self.events_cache: Cache = self.load_events_cache()

        self.page_size = max(
            1000, min(60_000, int(os.environ.get("AKAMAI_PAGE_SIZE", 60_000)))
        )  # default 1000, maximum 60000
        self.chunk_size = max(
            1, min(1000, int(os.environ.get("AKAMAI_CHUNK_SIZE", 1_000)))
        )  # number of events to accumulate before yielding to limit memory usage
        self.raw_log_max_length = max(512, int(os.environ.get("AKAMAI_RAW_LOG_MAX_LENGTH", 16_000)))
        self.log_count_max_keys = max(1000, int(os.environ.get("AKAMAI_LOG_COUNT_MAX_KEYS", 10_000)))
        # Reduce log noise: keep a bounded set of exception signatures that were already emitted.
        self._logged_exception_signatures: LRUCache[str, bool] = LRUCache(maxsize=self.log_count_max_keys)

    def _log_exception_once_per_signature(self, key: str, error: Exception, message: str) -> None:
        """Emit only the first error log for a strictly identical exception payload."""
        signature = "|".join(
            [
                key,
                type(error).__name__,
                self._sanitize_log_value(error),
                message,
            ]
        )
        # Explicit aggregation point: repeated identical errors are dropped after first emission.
        if signature not in self._logged_exception_signatures:
            self._logged_exception_signatures[signature] = True
            self.log_exception(
                error,
                message=message,
            )

    def load_events_cache(self) -> Cache:
        """Load cached event identifiers from checkpoint context."""
        result: LRUCache = LRUCache(maxsize=self.cache_size)

        with self.cursor._context as cache:
            events_ids = cache.get("events_cache", [])

        for event_id in events_ids:
            result[event_id] = True

        return result

    def save_events_cache(self) -> None:
        """Persist cached event identifiers into checkpoint context."""
        with self.cursor._context as cache:
            cache["events_cache"] = list(self.events_cache.keys())

    @cached_property
    def client(self) -> ApiClient:
        """Build and cache an authenticated Akamai API client."""
        return ApiClient(
            client_token=self.module.configuration.client_token,
            client_secret=self.module.configuration.client_secret,
            access_token=self.module.configuration.access_token,
        )

    @staticmethod
    def extract_attack_data(event: dict[str, Any]) -> dict[str, Any]:
        """Normalize attack data fields and decode per-rule values."""
        attack_section = event["attackData"]
        rules_array: list[dict[str, Any]] = []

        new_attack_section = {}
        for member in attack_section:
            if member[0:4] != "rule":
                new_attack_section[member] = attack_section[member]
                continue

            # Alternate field name converted from plural:
            member_as_singular = re.sub("s$", "", member)
            url_decoded = urllib.parse.unquote(attack_section[member])
            member_array = [item for item in url_decoded.split(";")]
            if not len(rules_array):
                for i in range(len(member_array)):
                    rules_array.append({})
            i = 0
            for item in member_array:
                rules_array[i][member_as_singular] = base64.b64decode(item).decode("utf-8", errors="backslashreplace")
                i += 1

            new_attack_section["rules"] = rules_array

        return new_attack_section

    @staticmethod
    def _extract_headers_with_diagnostics(headers: Any) -> tuple[dict[str, Any], dict[str, int]]:
        """Parse headers and collect malformed-line diagnostics."""
        result: dict[str, Any] = {}
        malformed_line_reasons: Counter[str] = Counter()

        if not isinstance(headers, str):
            malformed_line_reasons["invalid_type"] += 1
            return result, dict(malformed_line_reasons)

        for item in urllib.parse.unquote(headers).splitlines():
            item = item.strip()
            if not item:
                continue

            if ":" not in item:
                malformed_line_reasons["missing_separator"] += 1
                continue

            header_key, header_value = map(str.strip, item.split(":", maxsplit=1))
            if not header_key:
                malformed_line_reasons["empty_key"] += 1
                continue

            result[header_key] = header_value

        return result, dict(malformed_line_reasons)

    @staticmethod
    def extract_headers(headers: str) -> dict[str, Any]:
        """Parse headers and return only valid key-value pairs."""
        result, _ = AkamaiWAFLogsConnector._extract_headers_with_diagnostics(headers)
        return result

    @staticmethod
    def _sanitize_log_value(value: Any, max_length: int = 300) -> str:
        """Format a log value as a single, bounded line."""
        text = str(value)
        text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ").strip()
        if len(text) > max_length:
            return f"{text[:max_length]}..."
        return text

    def _serialize_raw_log_value(self, value: Any) -> str:
        """Serialize raw value for diagnostics with a configurable size cap."""
        try:
            serialized = orjson.dumps(value).decode("utf-8")
        except Exception:
            serialized = self._sanitize_log_value(value, max_length=self.raw_log_max_length)

        if len(serialized) > self.raw_log_max_length:
            return (
                f"{serialized[:self.raw_log_max_length]}"
                f"...[truncated_raw_log chars={len(serialized)} max_chars={self.raw_log_max_length}]"
            )

        return serialized

    @staticmethod
    def _get_event_request_id(event: dict[str, Any]) -> Any:
        """Extract requestId from an event HTTP message."""
        http_message = event.get("httpMessage")
        if isinstance(http_message, dict):
            return http_message.get("requestId")
        return None

    @staticmethod
    def _get_event_start_timestamp(event: dict[str, Any]) -> int | None:
        """Extract and cast event start timestamp to integer."""
        http_message = event.get("httpMessage")
        if not isinstance(http_message, dict):
            return None

        start = http_message.get("start")
        if start is None:
            return None

        try:
            return int(cast(Any, start))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_fallback_event_dedup_key(event: dict[str, Any]) -> str | None:
        """Build a deterministic deduplication key when requestId is unavailable."""
        try:
            canonical_payload = orjson.dumps(event, option=orjson.OPT_SORT_KEYS)
        except Exception:
            return None

        payload_hash = hashlib.sha256(canonical_payload).hexdigest()
        return f"fallback:{payload_hash}"

    def process_event(self, event: dict[str, Any]) -> None:
        """Normalize event sections and log header parsing anomalies."""
        # Processing `attackData` section
        new_attack_section = self.extract_attack_data(event)
        raw_http_message = event.get("httpMessage")
        if isinstance(raw_http_message, dict):
            http_message = raw_http_message
        else:
            self.log(
                message=(
                    "Skipped httpMessage normalization because httpMessage is not a mapping "
                    f"http_message_type={type(raw_http_message).__name__} "
                    f"raw_http_message={self._serialize_raw_log_value(raw_http_message)}"
                ),
                level="warning",
            )
            http_message = {}
            event["httpMessage"] = http_message

        # Processing `httpMessage` section
        raw_request_headers_value = http_message.get("requestHeaders")
        raw_response_headers_value = http_message.get("responseHeaders")

        request_headers = None
        request_malformed: dict[str, int] = {}
        if "requestHeaders" in http_message:
            request_headers, request_malformed = self._extract_headers_with_diagnostics(
                http_message.get("requestHeaders")
            )

        response_headers = None
        response_malformed: dict[str, int] = {}
        if "responseHeaders" in http_message:
            response_headers, response_malformed = self._extract_headers_with_diagnostics(
                http_message.get("responseHeaders")
            )

        event["attackData"] = new_attack_section
        if "requestHeaders" in http_message:
            event["httpMessage"]["requestHeaders"] = request_headers

        if "responseHeaders" in http_message:
            event["httpMessage"]["responseHeaders"] = response_headers

        ignored_request_lines = sum(request_malformed.values())
        ignored_response_lines = sum(response_malformed.values())
        if ignored_request_lines or ignored_response_lines:
            event_request_id = http_message.get("requestId")
            event_start = http_message.get("start")
            request_malformed_summary = self._sanitize_log_value(request_malformed)
            response_malformed_summary = self._sanitize_log_value(response_malformed)
            self.log(
                message=(
                    "Ignored malformed HTTP header lines "
                    f"event_request_id={self._sanitize_log_value(event_request_id)} "
                    f"event_start={self._sanitize_log_value(event_start)} "
                    f"request_header_lines_ignored={ignored_request_lines} "
                    f"response_header_lines_ignored={ignored_response_lines} "
                    f"request_malformed_reasons={request_malformed_summary} "
                    f"response_malformed_reasons={response_malformed_summary} "
                    f"raw_request_headers={self._serialize_raw_log_value(raw_request_headers_value)} "
                    f"raw_response_headers={self._serialize_raw_log_value(raw_response_headers_value)} "
                    f"raw_event={self._serialize_raw_log_value(event)}"
                ),
                level="warning",
            )

    def __fetch_next_events(self, from_date: int) -> Generator[list, None, None]:
        """Stream events from Akamai and yield chunked batches."""
        url = f"{self.module.configuration.base_url}/siem/v1/configs/{self.configuration.config_id}"
        self.log(
            message=(
                "Started fetching Akamai events "
                f"from_timestamp={from_date} page_size={self.page_size} chunk_size={self.chunk_size}"
            ),
            level="debug",
        )
        response = self.client.get(
            url=url, params={"from": from_date, "limit": self.page_size}, timeout=60, stream=True
        )

        while self.running:
            self.__handle_response_error(response)

            chunk: list = []
            offset = None
            events_in_page = 0

            for line in response.iter_lines():
                if line:
                    try:
                        item = orjson.loads(line)
                    except Exception:
                        self.log(
                            message=(
                                "Skipped malformed JSON line in Akamai stream "
                                f"line_size={len(line)} raw_line={line.decode('utf-8', errors='backslashreplace')}"
                            ),
                            level="warning",
                        )
                        continue

                    if not isinstance(item, dict):
                        self.log(
                            message=(
                                "Skipped non-object JSON line in Akamai stream "
                                f"line_size={len(line)} json_type={type(item).__name__} "
                                f"raw_line={line.decode('utf-8', errors='backslashreplace')} "
                                f"raw_item={self._serialize_raw_log_value(item)}"
                            ),
                            level="warning",
                        )
                        continue

                    if item.get("type") == "akamai_siem":
                        try:
                            self.process_event(item)
                        except Exception as error:
                            # Explicit aggregation point: identical process failures on identical raw events
                            # are logged once to avoid repetitive error spam across batches.
                            # Example for this call site:
                            # without safeguard, logs could look like:
                            # "Failed to process Akamai event event_request_id=99 raw_event={...}"
                            # "Failed to process Akamai event event_request_id=99 raw_event={...}"
                            # [...]
                            # "Failed to process Akamai event event_request_id=99 raw_event={...}"
                            # with safeguard, only the first line above is emitted.
                            self._log_exception_once_per_signature(
                                key="process_event_error",
                                error=error,
                                message=(
                                    "Failed to process Akamai event "
                                    f"event_request_id={self._sanitize_log_value(self._get_event_request_id(item))} "
                                    f"raw_event={self._serialize_raw_log_value(item)}"
                                ),
                            )
                            continue

                        chunk.append(item)
                        events_in_page += 1

                        if len(chunk) >= self.chunk_size:
                            INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(chunk))
                            yield chunk
                            chunk = []

                    else:
                        offset = item.get("offset")
                        total = item.get("total")
                        if offset is None:
                            self.log(
                                message=(
                                    "Skipped pagination context without offset "
                                    f"context_keys={self._sanitize_log_value(list(item.keys()))} "
                                    f"raw_context={self._serialize_raw_log_value(item)}"
                                ),
                                level="warning",
                            )
                            continue

                        # response context - last JSON line
                        if events_in_page > 0:
                            # Yield remaining events that didn't fill a full chunk
                            if chunk:
                                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(chunk))
                                yield chunk
                                chunk = []

                            self.log(
                                message=(
                                    "Processed Akamai events page "
                                    f"events_in_page={events_in_page} offset={offset} total={total}"
                                ),
                                level="debug",
                            )

                        else:
                            self.log(
                                message=(
                                    "No new Akamai events available "
                                    f"offset={offset} total={total} from_timestamp={from_date}"
                                ),
                                level="info",
                            )
                            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)
                            return

            if offset is None:
                flushed_events_in_final_chunk = 0
                if chunk:
                    flushed_events_in_final_chunk = len(chunk)
                    INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(
                        flushed_events_in_final_chunk
                    )
                    yield chunk
                    chunk = []

                self.log(
                    message=(
                        "Akamai stream ended without pagination context "
                        f"flushed_events_in_final_chunk={flushed_events_in_final_chunk} "
                        f"remaining_events_in_chunk={len(chunk)}"
                    ),
                    level="warning",
                )
                return

            response = self.client.get(
                url=url, params={"offset": offset, "limit": self.page_size}, timeout=60, stream=True
            )

    def fetch_events(self) -> Generator[list, None, None]:
        """Fetch events and update checkpoint timestamp when possible."""
        most_recent_date_seen: int = self.from_timestamp

        for next_events in self.__fetch_next_events(most_recent_date_seen):
            if next_events:
                timestamps = [
                    timestamp
                    for timestamp in (self._get_event_start_timestamp(event) for event in next_events)
                    if timestamp is not None
                ]

                if not timestamps:
                    self.log(
                        message=(
                            "Skipped checkpoint update because event timestamps are missing or invalid "
                            f"events_count={len(next_events)} "
                            f"raw_events={self._serialize_raw_log_value(next_events)}"
                        ),
                        level="warning",
                    )
                    yield next_events
                    continue

                latest_timestamp = max(timestamps)

                if latest_timestamp > most_recent_date_seen:
                    most_recent_date_seen = latest_timestamp

                # forward current events
                yield next_events

        # save the most recent date
        if most_recent_date_seen > self.from_timestamp:
            previous_from_timestamp = self.from_timestamp
            self.from_timestamp = most_recent_date_seen
            self.cursor.offset = most_recent_date_seen

            delta_time = datetime.now(timezone.utc).timestamp() - most_recent_date_seen
            current_lag = int(delta_time)
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)
            self.log(
                message=(
                    "Updated checkpoint after fetch "
                    f"previous_from_timestamp={previous_from_timestamp} "
                    f"new_from_timestamp={self.from_timestamp} lag_seconds={current_lag}"
                ),
                level="debug",
            )
        else:
            self.log(message=f"Kept checkpoint unchanged from_timestamp={self.from_timestamp}", level="debug")

    def __handle_response_error(self, response: requests.Response):
        """Log API error details and raise HTTP exceptions."""
        if not response.ok:
            request_method = response.request.method if response.request else None
            request_url = response.request.url if response.request else None
            safe_request_method = self._sanitize_log_value(request_method)
            safe_request_url = self._sanitize_log_value(request_url)
            message = (
                "Akamai API request failed "
                f"status={response.status_code} reason={self._sanitize_log_value(response.reason)} "
                f"method={safe_request_method} url={safe_request_url}"
            )
            self.log(
                message=message,
                level="error",
            )

            try:
                raw = response.json()
                api_error_client_ip = raw.get("clientIp")
                api_error_detail = raw.get("detail")
                api_error_instance = raw.get("instance")
                api_error_method = raw.get("method")
                api_error_request_id = raw.get("requestId")
                api_error_request_time = raw.get("requestTime")
                api_error_server_ip = raw.get("serverIp")
                api_error_title = raw.get("title")
                api_error_type = raw.get("type")

                self.log(
                    message=(
                        f"{message} "
                        "error_payload=true "
                        f"api_error_client_ip={self._sanitize_log_value(api_error_client_ip)} "
                        f"api_error_detail={self._sanitize_log_value(api_error_detail)} "
                        f"api_error_instance={self._sanitize_log_value(api_error_instance)} "
                        f"api_error_method={self._sanitize_log_value(api_error_method)} "
                        f"api_error_request_id={self._sanitize_log_value(api_error_request_id)} "
                        f"api_error_request_time={self._sanitize_log_value(api_error_request_time)} "
                        f"api_error_server_ip={self._sanitize_log_value(api_error_server_ip)} "
                        f"api_error_title={self._sanitize_log_value(api_error_title)} "
                        f"api_error_type={self._sanitize_log_value(api_error_type)}"
                    ),
                    level="error",
                )

            except Exception:
                self.log(
                    message=(
                        "Failed to parse Akamai API error response body "
                        f"status={response.status_code} reason={self._sanitize_log_value(response.reason)}"
                    ),
                    level="warning",
                )

            response.raise_for_status()

    def filter_processed_events(self, events: list[dict]) -> Generator[dict, None, None]:
        """Skip duplicates and yield only events to forward."""
        for event in events:
            event_id = self._get_event_request_id(event)
            if event_id is None:
                fallback_event_id = self._build_fallback_event_dedup_key(event)
                if fallback_event_id is None:
                    self.log(
                        message=(
                            "Forwarded event without deduplication because requestId is missing "
                            "and fallback dedup key generation failed "
                            f"raw_event={self._serialize_raw_log_value(event)}"
                        ),
                        level="warning",
                    )
                    yield event
                    continue

                if fallback_event_id in self.events_cache:
                    continue

                self.events_cache[fallback_event_id] = True
                self.log(
                    message=(
                        "Forwarded event with fallback deduplication because requestId is missing "
                        "dedup_marker=payload_hash "
                        f"raw_event={self._serialize_raw_log_value(event)}"
                    ),
                    level="warning",
                )
                yield event
                continue

            if event_id in self.events_cache:
                continue

            self.events_cache[event_id] = True
            yield event

    def next_batch(self):
        """Process one fetch-forward cycle and apply pacing."""
        # save the starting time
        batch_start_time = time.time()
        fetched_events = 0
        forwarded_events = 0
        deduplicated_events = 0
        processed_chunks = 0

        self.log(
            message=(
                "Started batch processing "
                f"from_timestamp={self.from_timestamp} frequency={self.configuration.frequency}"
            ),
            level="debug",
        )

        # Fetch next batch
        for events in self.fetch_events():
            processed_chunks += 1
            fetched_events += len(events)
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in self.filter_processed_events(events)]
            deduplicated_events += len(events) - len(batch_of_events)

            # if the batch is full, push it
            if len(batch_of_events) > 0:
                forwarded_events += len(batch_of_events)
                self.log(
                    message=(
                        "Forwarded events to intake "
                        f"forwarded_events={len(batch_of_events)} "
                        f"chunk_index={processed_chunks} fetched_events={len(events)} "
                        f"duplicate_events_skipped={len(events) - len(batch_of_events)}"
                    ),
                    level="info",
                )
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))

                self.push_events_to_intakes(events=batch_of_events)
                self.save_events_cache()

            else:
                self.log(
                    message=(
                        "Skipped forwarding chunk because all events were duplicates "
                        f"chunk_index={processed_chunks} fetched_events={len(events)}"
                    ),
                    level="info",
                )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(
            message=(
                "Completed batch processing "
                f"duration_seconds={batch_duration} chunks={processed_chunks} "
                f"fetched_events={fetched_events} forwarded_events={forwarded_events} "
                f"duplicate_events_skipped={deduplicated_events}"
            ),
            level="debug",
        )
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(
                message=(
                    "Waiting before next batch "
                    f"sleep_seconds={delta_sleep} frequency={self.configuration.frequency} "
                    f"last_batch_duration={batch_duration}"
                ),
                level="debug",
            )
            time.sleep(delta_sleep)
        else:
            self.log(
                message=(
                    "Starting next batch immediately "
                    f"frequency={self.configuration.frequency} last_batch_duration={batch_duration}"
                ),
                level="debug",
            )

    def run(self):  # pragma: no cover
        """Run batch processing loop until connector stops."""
        self.log(message="Started Akamai WAF logs connector component=akamai_waf_logs", level="info")

        while self.running:
            try:
                self.next_batch()
            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
