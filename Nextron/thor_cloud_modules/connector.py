import json
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

    def _load_processed(self) -> dict[str, Optional[float]]:
        """Return creation epochs for processed scans; ``None`` means retain indefinitely."""
        with self._context as cache:
            return dict(cache.get("processed_scans") or {})

    def _save_processed(self, processed: dict[str, Optional[float]]) -> None:
        with self._context as cache:
            cache["processed_scans"] = processed

    def _load_pruned_range(self) -> tuple[Optional[float], Optional[float]]:
        """Return ``(covered_since, pruned_until)``; both ``None`` before the first poll.

        Processed-scan entries are pruned once they leave the lookback window. Every
        scan created in ``[covered_since, pruned_until)`` was inside an earlier window,
        so it was either forwarded (and its entry pruned) or deliberately left behind.
        Such scans must not be forwarded again when the window is enlarged.
        """
        with self._context as cache:
            return cache.get("covered_since"), cache.get("pruned_until")

    def _save_pruned_range(self, covered_since: float, pruned_until: float) -> None:
        with self._context as cache:
            cache["covered_since"] = covered_since
            cache["pruned_until"] = pruned_until

    @staticmethod
    def _in_pruned_range(
        created: Optional[float], covered_since: Optional[float], pruned_until: Optional[float]
    ) -> bool:
        if created is None or covered_since is None or pruned_until is None:
            return False
        return covered_since <= created < pruned_until

    def _wait(self, seconds: float) -> None:
        """Sleep between polls, but return as soon as the connector is asked to stop."""
        self._stop_event.wait(seconds)

    def _forward_scan(self, base_url: str, headers: dict, scan: dict) -> bool:
        """Forward the logs of one finished scan.

        Returns True when the scan is done and must not be checked again, False when
        it has to be retried on a later poll.
        """
        scan_id = scan["id"]
        status = str(scan.get("status") or "").lower()

        # THOR Cloud encrypts the logs with the account's public key when the campaign
        # enables log encryption. They can't be parsed, so there is nothing to forward.
        if scan.get("logs_encrypted"):
            self.log(
                message=f"Scan {scan_id} has encrypted logs, which can't be forwarded; skipping it",
                level="warning",
            )
            return True

        # A finished scan that produced no JSON log has nothing to forward.
        if "thor.json" not in (scan.get("available_logs") or []):
            self.log(
                message=f"Scan {scan_id} (status={status!r}) has no thor.json; marking processed",
                level="debug",
            )
            return True

        self.log(message=f"Fetching logs for scan {scan_id}", level="debug")
        try:
            logs = client.fetch_scan_logs(base_url, headers, scan_id)
        except requests.RequestException as e:
            self.log_exception(e, message=f"Failed to fetch logs for scan {scan_id}")
            return False

        if not logs:
            return True

        events = [json.dumps(log) for log in logs]
        event_ids = self.push_events_to_intakes(events=events)

        # push_events_to_intakes() does not raise when a chunk can't be delivered: it
        # logs the error and returns fewer event IDs. Only treat the scan as forwarded
        # when every event was accepted, otherwise retry it on the next poll.
        if len(event_ids or []) != len(events):
            self.log(
                message=(
                    f"Only {len(event_ids or [])} of {len(events)} events of scan {scan_id} were accepted "
                    "by the intake; the scan will be forwarded again on the next poll"
                ),
                level="error",
            )
            return False

        self.log(message=f"{len(events)} events collected from scan {scan_id}", level="info")
        return True

    def run(self) -> None:
        """Main connector execution logic"""
        self.log(message="Starting THOR Cloud connector", level="info")

        while self.running:
            try:
                if not self.module.configuration.api_key:
                    self.log(message="API key is required", level="error")
                    self._wait(60)
                    continue

                base_url = client.get_base_url(self.configuration.product)
                headers = client.get_headers(self.module.configuration.api_key)

                self.log(message=f"Fetching scans from {base_url}", level="info")

                try:
                    scans = client.fetch_scans(
                        base_url,
                        headers,
                        self.configuration.days_back,
                        client.parse_campaigns(self.configuration.campaigns),
                    )
                except requests.RequestException as e:
                    self.log_exception(e, message="Failed to fetch scans")
                    self._wait(60)
                    continue

                # Deduplicate against scans already forwarded (persisted across runs).
                # Scans whose entries were pruned in an earlier poll are recognized by
                # the pruned range, so enlarging Days Back does not forward them again.
                cutoff = (datetime.now(timezone.utc) - timedelta(days=self.configuration.days_back)).timestamp()
                covered_since, pruned_until = self._load_pruned_range()
                loaded_processed = self._load_processed()

                new_scans = [
                    s
                    for s in scans
                    if s.get("id")
                    and s["id"] not in loaded_processed
                    and not self._in_pruned_range(client.scan_creation_epoch(s), covered_since, pruned_until)
                ]

                # Prune entries older than the lookback window to bound state size, and
                # widen the pruned range accordingly.
                processed = {sid: ts for sid, ts in loaded_processed.items() if ts is None or ts >= cutoff}
                if processed != loaded_processed:
                    self._save_processed(processed)
                self._save_pruned_range(
                    covered_since=cutoff if covered_since is None else min(covered_since, cutoff),
                    pruned_until=cutoff if pruned_until is None else max(pruned_until, cutoff),
                )
                self.log(
                    message=f"Found {len(scans)} scans ({len(new_scans)} new to forward)",
                    level="info",
                )

                for scan in new_scans:
                    if not self.running:
                        break

                    # Pull results only for terminal scans (successful or failed);
                    # a running scan is postponed and re-checked on a later poll once
                    # it has finished. Any other (not-yet-terminal) state is postponed
                    # too, so we never drop a scan that may still produce logs.
                    status = str(scan.get("status") or "").lower()
                    if status not in ("successful", "failed"):
                        self.log(
                            message=f"Scan {scan['id']} not finished (status={status!r}); will re-check on a later poll",
                            level="debug",
                        )
                        continue

                    # Forward and persist one scan at a time: this bounds memory to a
                    # single scan's log and avoids resending scans that were already
                    # delivered if the connector stops in the middle of a poll.
                    if self._forward_scan(base_url, headers, scan):
                        processed[scan["id"]] = client.scan_creation_epoch(scan)
                        self._save_processed(processed)

                self._wait(self.configuration.polling_interval * 60)

            except Exception as e:
                self.log_exception(e, message="Connector error")
                self._wait(self.configuration.polling_interval * 60)
