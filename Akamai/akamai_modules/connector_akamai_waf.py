import base64
import os
import re
import time
import urllib.parse
from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Any, Generator

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

    def load_events_cache(self) -> Cache:
        result: LRUCache = LRUCache(maxsize=self.cache_size)

        with self.cursor._context as cache:
            events_ids = cache.get("events_cache", [])

        for event_id in events_ids:
            result[event_id] = True

        return result

    def save_events_cache(self) -> None:
        with self.cursor._context as cache:
            cache["events_cache"] = list(self.events_cache.keys())

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            client_token=self.module.configuration.client_token,
            client_secret=self.module.configuration.client_secret,
            access_token=self.module.configuration.access_token,
        )

    @staticmethod
    def extract_attack_data(event: dict[str, Any]) -> dict[str, Any]:
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
        result = {}
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
        result, _ = AkamaiWAFLogsConnector._extract_headers_with_diagnostics(headers)
        return result

    def process_event(self, event: dict[str, Any]) -> None:
        # Processing `attackData` section
        new_attack_section = self.extract_attack_data(event)
        http_message = event.get("httpMessage", {})

        # Processing `httpMessage` section
        request_headers = None
        request_malformed = {}
        if "requestHeaders" in http_message:
            request_headers, request_malformed = self._extract_headers_with_diagnostics(
                http_message.get("requestHeaders")
            )

        response_headers = None
        response_malformed = {}
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
            self.log(
                message=(
                    "Ignored malformed HTTP header lines "
                    f"event_request_id={event_request_id} "
                    f"event_start={event_start} "
                    f"request_header_lines_ignored={ignored_request_lines} "
                    f"response_header_lines_ignored={ignored_response_lines} "
                    f"request_malformed_reasons={request_malformed} "
                    f"response_malformed_reasons={response_malformed}"
                ),
                level="warning",
            )

    def __fetch_next_events(self, from_date: int) -> Generator[list, None, None]:
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
                    item: dict = orjson.loads(line)
                    if item.get("type") == "akamai_siem":
                        self.process_event(item)
                        chunk.append(item)
                        events_in_page += 1

                        if len(chunk) >= self.chunk_size:
                            INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(chunk))
                            yield chunk
                            chunk = []

                    else:
                        offset = item["offset"]
                        total = item.get("total")
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
                if chunk:
                    INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(chunk))
                    yield chunk

                self.log(
                    message=(
                        "Akamai stream ended without pagination context "
                        f"remaining_events_in_chunk={len(chunk)}"
                    ),
                    level="warning",
                )
                return

            response = self.client.get(
                url=url, params={"offset": offset, "limit": self.page_size}, timeout=60, stream=True
            )

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_date_seen: int = self.from_timestamp

        for next_events in self.__fetch_next_events(most_recent_date_seen):
            if next_events:
                latest_event = max(next_events, key=lambda x: int(x["httpMessage"]["start"]))
                latest_timestamp = int(latest_event["httpMessage"]["start"])

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
            self.log(
                message=f"Kept checkpoint unchanged from_timestamp={self.from_timestamp}",
                level="debug",
            )

    def __handle_response_error(self, response: requests.Response):
        if not response.ok:
            request_method = response.request.method if response.request else None
            request_url = response.request.url if response.request else None
            message = (
                "Akamai API request failed "
                f"status={response.status_code} reason={response.reason} method={request_method} url={request_url}"
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
                        f"api_error_client_ip={api_error_client_ip} "
                        f"api_error_detail={api_error_detail} "
                        f"api_error_instance={api_error_instance} "
                        f"api_error_method={api_error_method} "
                        f"api_error_request_id={api_error_request_id} "
                        f"api_error_request_time={api_error_request_time} "
                        f"api_error_server_ip={api_error_server_ip} "
                        f"api_error_title={api_error_title} "
                        f"api_error_type={api_error_type}"
                    ),
                    level="error",
                )

            except Exception:
                self.log(
                    message=(
                        "Failed to parse Akamai API error response body "
                        f"status={response.status_code} reason={response.reason}"
                    ),
                    level="warning",
                )

            response.raise_for_status()

    def filter_processed_events(self, events: list[dict]) -> Generator[dict, None, None]:
        for event in events:
            event_id = event["httpMessage"]["requestId"]
            if event_id in self.events_cache:
                continue

            self.events_cache[event_id] = True
            yield event

    def next_batch(self):
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
        self.log(message="Started Akamai WAF logs connector component=akamai_waf_logs", level="info")

        while self.running:
            try:
                self.next_batch()
            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
