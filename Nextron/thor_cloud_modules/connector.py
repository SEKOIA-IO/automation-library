import json
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

import requests
from pydantic import ConfigDict, Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from thor_cloud_modules import client

if TYPE_CHECKING:
    from . import ThorCloudModule


class ThorCloudConnectorConfiguration(DefaultConnectorConfiguration):
    # Sekoia renders enum fields using the property KEY as the label (it ignores
    # `title` for enums), so the key is "Product"; the alias keeps the Python
    # attribute snake_case (`self.configuration.product`). populate_by_name lets
    # code and tests construct with `product=` too.
    model_config = ConfigDict(populate_by_name=True)

    product: str = Field(
        default="thor_cloud_lite",
        alias="Product",
        description="THOR Cloud product",
        json_schema_extra={
            "enum": ["thor_cloud", "thor_cloud_lite"],
            "enumNames": ["THOR Cloud", "THOR Cloud Lite"],
        },
    )
    polling_interval: int = Field(
        default=60,
        description="Polling interval in minutes",
    )
    days_back: int = Field(default=7, description="Days to look back for scans")
    campaigns: Optional[str] = Field(
        default=None, description="Comma-separated campaign UUIDs to monitor (empty = all campaigns)"
    )


class ThorCloudConnector(Connector):
    """Connector to pull logs from THOR Cloud or THOR Cloud Lite"""

    module: "ThorCloudModule"
    configuration: ThorCloudConnectorConfiguration
    push_event_rate: int = 10

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Persisted across restarts: remembers which scans were already forwarded
        # so their logs are never re-ingested on subsequent polls.
        self._context = PersistentJSON("context.json", self.data_path)

    def _load_processed(self) -> dict[str, float]:
        """Return {scan_id: creation_epoch} of scans already forwarded."""
        with self._context as cache:
            return dict(cache.get("processed_scans") or {})

    def _save_processed(self, processed: dict[str, float]) -> None:
        with self._context as cache:
            cache["processed_scans"] = processed

    def run(self) -> None:
        """Main connector execution logic"""
        self.log(message="Starting THOR Cloud connector", level="info")

        while self.running:
            try:
                if not self.module.configuration.api_key:
                    self.log(message="API key is required", level="error")
                    time.sleep(60)
                    continue

                base_url = client.get_base_url(self.configuration.product)
                headers = client.get_headers(self.module.configuration.api_key)

                self.log(message=f"Fetching scans from {base_url}", level="info")

                try:
                    scans = client.fetch_scans(
                        base_url, headers, self.configuration.days_back, client.parse_campaigns(self.configuration.campaigns)
                    )
                except requests.RequestException as e:
                    self.log_exception(e, message="Failed to fetch scans")
                    time.sleep(60)
                    continue

                # Deduplicate against scans already forwarded (persisted across runs),
                # pruning entries older than the lookback window to bound state size.
                cutoff = (datetime.now(timezone.utc) - timedelta(days=self.configuration.days_back)).timestamp()
                processed = {sid: ts for sid, ts in self._load_processed().items() if ts >= cutoff}

                new_scans = [s for s in scans if s.get("id") and s["id"] not in processed]
                self.log(
                    message=f"Found {len(scans)} scans ({len(new_scans)} new to forward)",
                    level="info",
                )

                batch_of_events = []
                forwarded_ids: dict[str, float] = {}
                for scan in new_scans:
                    scan_id = scan["id"]

                    # Pull results only for terminal scans (successful or failed);
                    # a running scan is postponed and re-checked on a later poll once
                    # it has finished. Any other (not-yet-terminal) state is postponed
                    # too, so we never drop a scan that may still produce logs.
                    status = str(scan.get("status") or "").lower()
                    if status not in ("successful", "failed"):
                        self.log(
                            message=f"Scan {scan_id} not finished (status={status!r}); will re-check on a later poll",
                            level="debug",
                        )
                        continue

                    # Terminal scan: pull its JSON log if one was produced. If there is
                    # nothing to fetch, remember it so we stop re-checking it.
                    available = scan.get("available_logs") or []
                    if "thor.json" not in available:
                        self.log(
                            message=f"Scan {scan_id} (status={status!r}) has no thor.json; marking processed",
                            level="debug",
                        )
                        forwarded_ids[scan_id] = client.scan_creation_epoch(scan) or cutoff
                        continue

                    self.log(message=f"Fetching logs for scan {scan_id}", level="debug")
                    try:
                        logs = client.fetch_scan_logs(base_url, headers, scan_id)
                    except requests.RequestException as e:
                        self.log_exception(e, message=f"Failed to fetch logs for scan {scan_id}")
                        continue  # do not mark processed; retry on the next run

                    for log in logs:
                        batch_of_events.append(json.dumps(log))
                    forwarded_ids[scan_id] = client.scan_creation_epoch(scan) or cutoff

                if batch_of_events:
                    self.log(message=f"{len(batch_of_events)} events collected", level="info")
                    self.push_events_to_intakes(events=batch_of_events)

                # Persist only after a successful push so failed scans are retried.
                if forwarded_ids:
                    processed.update(forwarded_ids)
                    self._save_processed(processed)

                time.sleep(self.configuration.polling_interval * 60)

            except Exception as e:
                self.log_exception(e, message="Connector error")
