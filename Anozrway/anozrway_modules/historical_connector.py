from __future__ import annotations

from asyncio import sleep
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
import hashlib

from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from anozrway_modules.client.http_client import AnozrwayClient
from anozrway_modules.client.errors import AnozrwayAuthError

from anozrway_modules.metrics import (
    api_requests,
    api_request_duration,
    events_collected,
    events_forwarded,
    events_duplicated,
    checkpoint_age,
)


class AnozrwayHistoricalConfiguration(DefaultConnectorConfiguration):
    """Connector-specific configuration (Anozrway Balise Pipeline)"""

    intake_server: Optional[str] = None
    intake_key: str = ""

    frequency: int = 3600
    chunk_size: int = 1000

    context: str = "demo"
    domains: str = ""
    lookback_days: int = 7
    window_seconds: int = 3600


class AnozrwayHistoricalConnector(AsyncConnector):
    """
    Connector to fetch leak detection events from the Anozrway Balise Pipeline
    and forward them to Sekoia intake.
    """

    name = "AnozrwayHistorical"
    configuration: AnozrwayHistoricalConfiguration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.context_store = PersistentJSON("context.json", self._data_path)
        self.event_cache_store = PersistentJSON("event_cache.json", self._data_path)
        self.event_cache_ttl = timedelta(hours=48)

        self.log(
            message=(
                f"AnozrwayHistoricalConnector initialized - "
                f"Data path: {self._data_path}, "
                f"Frequency: {self.configuration.frequency}s, "
                f"Chunk size: {self.configuration.chunk_size}, "
                f"Window: {self.configuration.window_seconds}s"
            ),
            level="info",
        )

    def _parse_domains(self) -> List[str]:
        raw = (self.configuration.domains or "").strip()
        return [d.strip() for d in raw.split(",") if d.strip()]

    # ---------------------------------------------------------------------
    # Checkpoint management (based on event timestamp / last_updated)
    # ---------------------------------------------------------------------
    def last_checkpoint(self) -> datetime:
        """
        Return last checkpoint timestamp.
        If undefined, start from now - lookback_days.
        """
        default_start = datetime.now(timezone.utc) - timedelta(days=int(self.configuration.lookback_days))

        with self.context_store as c:
            ts = c.get("last_checkpoint")
            if ts:
                try:
                    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
                except Exception:
                    return default_start

        return default_start

    def save_checkpoint(self, last_seen: datetime) -> None:
        checkpoint_time = last_seen.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        run_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        with self.context_store as c:
            c["last_checkpoint"] = checkpoint_time
            c["last_successful_run"] = run_time

        # metrics
        age = max(0.0, (datetime.now(timezone.utc) - last_seen).total_seconds())
        checkpoint_age.set(age)

    # ---------------------------------------------------------------------
    # Cache management
    # ---------------------------------------------------------------------
    def _cleanup_event_cache(self) -> None:
        cutoff = datetime.now(timezone.utc) - self.event_cache_ttl

        with self.event_cache_store as s:
            keys = list(s.keys())
            for k in keys:
                try:
                    ts = datetime.fromisoformat(str(s[k]).replace("Z", "+00:00")).astimezone(timezone.utc)
                    if ts < cutoff:
                        del s[k]
                except Exception:
                    del s[k]

    @staticmethod
    def _safe_str(x: Any) -> str:
        if x is None:
            return ""
        return str(x)

    @classmethod
    def _extract_event_ts(cls, event: Dict[str, Any]) -> Optional[datetime]:
        """
        Extract a stable event timestamp from a Balise Pipeline event.
        Priority: timestamp -> last_updated.
        """
        ts = event.get("timestamp") or event.get("last_updated")
        if not ts:
            return None
        try:
            return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            return None

    @classmethod
    def _extract_entity_id(cls, event: Dict[str, Any]) -> str:
        """
        Pick the most stable identifier for a Balise Pipeline event.
        """
        return cls._safe_str(event.get("nom_fuite")).strip().lower()

    @classmethod
    def _compute_dedup_key(cls, searched_domain: str, event: Dict[str, Any]) -> str:
        """
        Build a stable dedup key for Balise Pipeline events.
        Based on: searched_domain + nom_fuite + timestamp.
        """
        nom_fuite = cls._safe_str(event.get("nom_fuite")).strip().lower()
        ts = cls._extract_event_ts(event)
        ts_s = ts.isoformat().replace("+00:00", "Z") if ts else ""

        raw = "|".join(
            [
                searched_domain.strip().lower(),
                nom_fuite,
                ts_s,
            ]
        )

        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _is_new_event(self, cache_key: str) -> bool:
        with self.event_cache_store as s:
            if cache_key in s:
                events_duplicated.inc()
                return False

            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            s[cache_key] = now_iso
            return True

    # ---------------------------------------------------------------------
    # Main fetch
    # ---------------------------------------------------------------------
    async def fetch_events(self, client: AnozrwayClient) -> AsyncGenerator[List[Dict[str, Any]], None]:
        self._cleanup_event_cache()

        domains = self._parse_domains()
        if not domains:
            self.log(message="No domains configured. Nothing to collect.", level="warning")
            return

        # time boundaries
        start = self.last_checkpoint()
        end = datetime.now(timezone.utc) - timedelta(minutes=2)

        if start >= end:
            self.log(message="Checkpoint is up-to-date. No new data to collect.", level="info")
            return

        window = timedelta(seconds=int(self.configuration.window_seconds))
        max_seen_ts: Optional[datetime] = None

        current = start
        while current < end:
            window_end = min(current + window, end)

            for domain in domains:
                t0 = datetime.now().timestamp()
                status: Any = "error"
                try:
                    records = await client.fetch_events(
                        context=self.configuration.context,
                        domain=domain,
                        start_date=current,
                        end_date=window_end,
                    )
                    status = 200
                except Exception as e:
                    status = getattr(e, "status", None) or "error"
                    api_requests.labels(endpoint="events", status_code=str(status)).inc()
                    self.log_exception(e, message=f"Error while fetching Balise events for domain={domain}")
                    continue
                finally:
                    dt = datetime.now().timestamp() - t0
                    api_request_duration.labels(endpoint="events").observe(dt)

                api_requests.labels(endpoint="events", status_code=str(status)).inc()

                if not records:
                    continue

                events_collected.inc(len(records))

                batch: List[Dict[str, Any]] = []
                for ev in records:
                    if not isinstance(ev, dict):
                        continue

                    key = self._compute_dedup_key(domain, ev)
                    if not self._is_new_event(key):
                        continue

                    # Attach context for downstream parsing/intake routing.
                    ev = dict(ev)
                    ev["_searched_domain"] = domain
                    ev["_context"] = self.configuration.context

                    # Normalize download links if they come quoted.
                    dl = ev.get("download_links")
                    if isinstance(dl, list):
                        cleaned: List[Any] = []
                        for item in dl:
                            if isinstance(item, str):
                                s = item.strip()
                                if s.startswith('"') and s.endswith('"') and len(s) >= 2:
                                    s = s[1:-1]
                                cleaned.append(s)
                            else:
                                cleaned.append(item)
                        ev["download_links"] = cleaned

                    ev_ts = self._extract_event_ts(ev)
                    if ev_ts and ((max_seen_ts is None) or (ev_ts > max_seen_ts)):
                        max_seen_ts = ev_ts

                    batch.append(ev)

                    if len(batch) >= int(self.configuration.chunk_size):
                        yield batch
                        batch = []

                if batch:
                    yield batch

            current = window_end

        # update checkpoint (avoid reread if inclusive)
        if max_seen_ts:
            self.save_checkpoint(max_seen_ts + timedelta(seconds=1))

    async def next_batch(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        async with AnozrwayClient(module_config=self.module.configuration, trigger=self) as client:
            async for batch in self.fetch_events(client):
                yield batch

    def run(self):  # pragma: no cover
        import asyncio
        import signal

        loop = asyncio.get_event_loop()

        def handle_stop_signal():
            loop.create_task(self.shutdown())

        loop.add_signal_handler(signal.SIGTERM, handle_stop_signal)
        loop.add_signal_handler(signal.SIGINT, handle_stop_signal)

        try:
            loop.run_until_complete(self._async_run())
        except AnozrwayAuthError as e:
            self.log_exception(e, message="CRITICAL: Authentication failed - Check credentials")
        except Exception as e:
            self.log_exception(e, message="Unexpected error in connector execution")
        finally:
            loop.close()

    async def _async_run(self):
        while self.running:
            try:
                batch_count = 0
                async for batch in self.next_batch():
                    batch_count += 1
                    self.log(message=f"Pushing batch {batch_count} to intake - Events: {len(batch)}", level="info")
                    await self.push_data_to_intakes(events=batch)
                    events_forwarded.inc(len(batch))

                await sleep(int(self.configuration.frequency))
            except AnozrwayAuthError:
                raise
            except Exception as e:
                self.log_exception(e, message="Error in collection loop - retry in 60s")
                await sleep(60)
