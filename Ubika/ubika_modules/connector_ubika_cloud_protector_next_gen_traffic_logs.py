import time
from datetime import datetime, timezone

import orjson
from pydantic.v1 import Field

from ubika_modules.client.auth import AuthorizationError, AuthorizationTimeoutError

from .connector_ubika_cloud_protector_next_gen_base import (
    UbikaCloudProtectorNextGenBaseConnector,
    UbikaCloudProtectorNextGenBaseConnectorConfiguration,
)


class UbikaCloudProtectorNextGenTrafficLogsConnectorConfiguration(
    UbikaCloudProtectorNextGenBaseConnectorConfiguration
):
    # Back-fill window on first run, in hours
    start_time: int = Field(1, description="The number of hours from which events should be queried", ge=0)


class UbikaCloudProtectorNextGenTrafficLogsConnector(UbikaCloudProtectorNextGenBaseConnector):
    """
    Connector that continuously polls the Ubika Cloud Protector NextGen
    traffic-logs endpoint and forwards them to the configured intake.
    """

    NAME: str = "Ubika Cloud Protector NextGen Traffic Logs"
    configuration: UbikaCloudProtectorNextGenTrafficLogsConnectorConfiguration

    def process_batch(self, start_ts: int) -> int:
        """
        Fetch pages from start_ts, publish each, update and persist the max timestamp.
        Returns the new max timestamp to use for the next iteration.
        """
        max_ts = start_ts
        for page in self._get_pages(
            endpoint="traffic-logs",
            params={
                "filters.fromDate": start_ts,
                "pagination.pageSize": self.configuration.chunk_size,
                "pagination.realtime": True,
            },
        ):
            out_payloads: list[str] = []
            for evt in page:
                # Serialize each page
                serialized = orjson.dumps(evt).decode()
                out_payloads.append(serialized)

                # Update the highest timestamp seen
                # This way we never re-consume older logs (we always move "forward" in time)
                # and we survive restarts because the last-seen timestamp is persisted on disk
                try:
                    ts = int(evt.get("timestamp", 0))
                except (TypeError, ValueError):
                    ts = 0
                if ts > max_ts:
                    max_ts = ts

            # Publish if we saw anything
            if out_payloads:
                self.log(f"Publishing {len(out_payloads)} traffic-log events", level="info")
                self.push_events_to_intakes(events=out_payloads)

        # Persist new checkpoint after exhausting all pages of new logs
        with self.context as cache:
            cache["most_recent_timestamp_seen"] = max_ts

        return max_ts

    def run(self) -> None:
        """
        Main loop:
        1) Load last checkpoint (milliseconds since epoch)
        2) Fetch pages of new logs via _get_pages()
        3) For each page:
            - publish to intake
            - track highest timestamp seen
        4) Save new checkpoint
        5) Sleep for `frequency` seconds and repeat
        """
        self.log(f"Start fetching {self.NAME} events", level="info")

        # Initialize or load checkpoint
        with self.context as cache:
            # Read the last checkpoint (ms since epoch)
            # from the <self.data_path>/context.json file (PersistentJSON)
            last_ts = cache.get("most_recent_timestamp_seen")
        if not last_ts or last_ts <= 0:
            # If no valid checkpoint is found, back-fill X hours on first run
            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            backfill_ms = self.configuration.start_time * 3600 * 1000
            last_ts = now_ms - backfill_ms
        self.log(f"Initial start timestamp: {last_ts}", level="debug")

        try:
            # Polling loop
            while self.running:
                start_time = time.time()
                # Process one batch of pages and get updated checkpoint
                try:
                    last_ts = self.process_batch(start_ts=last_ts)
                except (AuthorizationError, AuthorizationTimeoutError):
                    # Let authorization errors bubble up to trigger connector disablement and alerting
                    raise
                except Exception as e:
                    self.log_exception(e, message="Error fetching traffic logs")
                finally:
                    # Sleep before next poll, but wake immediately if stop is requested
                    elapsed = time.time() - start_time
                    self.log(f"Iteration took {elapsed:.2f}s, sleeping {self.configuration.frequency}s", level="debug")
                    self._stop_event.wait(self.configuration.frequency)
        finally:
            # Cleanup on stop or fatal error
            self.client.close()
            with self.context as cache:
                cache["most_recent_timestamp_seen"] = last_ts
            self.log(f"Stopped fetching {self.NAME} events", level="info")
