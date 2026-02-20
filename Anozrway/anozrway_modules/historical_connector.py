from __future__ import annotations

import hashlib
from asyncio import sleep
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import orjson
from dateutil.parser import isoparse
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from anozrway_modules.client.errors import AnozrwayAuthError
from anozrway_modules.client.http_client import AnozrwayClient
from anozrway_modules.metrics import (
    api_request_duration,
    api_requests,
    checkpoint_age,
    events_collected,
    events_duplicated,
    events_forwarded,
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


class AnozrwayHistoricalConnector(AsyncConnector):
    """
    Connector to fetch leak detection events from the Anozrway Balise Pipeline
    and forward them to Sekoia intake.
    """

    name = "AnozrwayHistorical"
    configuration: AnozrwayHistoricalConfiguration

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.context_store = PersistentJSON("context.json", self._data_path)
        self.event_cache_store = PersistentJSON("event_cache.json", self._data_path)
        self.event_cache_ttl = timedelta(hours=48)

        self.log(
            message=(
                f"AnozrwayHistoricalConnector initialized - "
                f"Data path: {self._data_path}, "
                f"Frequency: {self.configuration.frequency}s, "
                f"Chunk size: {self.configuration.chunk_size}"
            ),
            level="info",
        )

    def _parse_domains(self) -> List[str]:
        raw = (self.configuration.domains or "").strip()
        return [d.strip() for d in raw.split(",") if d.strip()]

    # ------------------------------------------------------------------
    # Checkpoint management
    # ------------------------------------------------------------------
    def last_checkpoint(self) -> datetime:
        """Return last checkpoint timestamp; default = now - lookback_days."""
        default_start = datetime.now(timezone.utc) - timedelta(days=int(self.configuration.lookback_days))

        with self.context_store as c:
            ts = c.get("last_checkpoint")
            if ts:
                try:
                    return isoparse(str(ts)).astimezone(timezone.utc)
                except Exception as exc:
                    self.log(
                        message=f"Invalid checkpoint timestamp '{ts}', falling back to default: {exc}",
                        level="warning",
                    )
                    return default_start

        return default_start

    def save_checkpoint(self, last_seen: datetime) -> None:
        checkpoint_time = last_seen.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        run_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        with self.context_store as c:
            c["last_checkpoint"] = checkpoint_time
            c["last_successful_run"] = run_time

        age = max(0.0, (datetime.now(timezone.utc) - last_seen).total_seconds())
        checkpoint_age.labels(intake_key=self.configuration.intake_key).set(age)

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------
    def _cleanup_event_cache(self) -> None:
        cutoff = datetime.now(timezone.utc) - self.event_cache_ttl

        with self.event_cache_store as s:
            keys = list(s.keys())
            for k in keys:
                try:
                    ts = isoparse(str(s[k])).astimezone(timezone.utc)
                    if ts < cutoff:
                        del s[k]
                except Exception as exc:
                    self.log(message=f"Invalid cache entry '{k}', removing: {exc}", level="debug")
                    del s[k]

    @staticmethod
    def _safe_str(x: Any) -> str:
        if x is None:
            return ""
        return str(x)

    def _extract_event_ts(self, event: Dict[str, Any]) -> Optional[datetime]:
        """Extract a stable event timestamp. Priority: timestamp -> last_updated."""
        ts = event.get("timestamp") or event.get("last_updated")
        if not ts:
            return None
        try:
            return isoparse(str(ts)).astimezone(timezone.utc)
        except Exception as exc:
            self.log(message=f"Failed to parse event timestamp '{ts}': {exc}", level="debug")
            return None

    @classmethod
    def _extract_entity_id(cls, event: Dict[str, Any]) -> str:
        return cls._safe_str(event.get("nom_fuite")).strip().lower()

    def _compute_dedup_key(self, searched_domain: str, event: Dict[str, Any]) -> str:
        """Build a stable dedup key: searched_domain + nom_fuite + timestamp."""
        nom_fuite = self._safe_str(event.get("nom_fuite")).strip().lower()
        ts = self._extract_event_ts(event)
        if ts:
            ts_s = ts.isoformat().replace("+00:00", "Z")
        else:
            # fallback to raw timestamp string to avoid collapsing distinct events
            ts_s = self._safe_str(event.get("timestamp") or event.get("last_updated"))

        raw = "|".join([searched_domain.strip().lower(), nom_fuite, ts_s])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _is_new_event(self, cache_key: str) -> bool:
        with self.event_cache_store as s:
            if cache_key in s:
                events_duplicated.labels(intake_key=self.configuration.intake_key).inc()
                return False

            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            s[cache_key] = now_iso
            return True

    # ------------------------------------------------------------------
    # Main fetch
    # ------------------------------------------------------------------
    async def fetch_events(self, client: AnozrwayClient) -> AsyncGenerator[List[Dict[str, Any]], None]:
        self._cleanup_event_cache()

        domains = self._parse_domains()
        if not domains:
            self.log(message="No domains configured. Nothing to collect.", level="warning")
            return

        # Use frequency as the single time window (no sub-windowing)
        start = self.last_checkpoint()
        end = datetime.now(timezone.utc) - timedelta(minutes=2)

        if start >= end:
            self.log(message="Checkpoint is up-to-date. No new data to collect.", level="info")
            return

        intake_key = self.configuration.intake_key
        max_seen_ts: Optional[datetime] = None

        for domain in domains:
            t0 = datetime.now().timestamp()
            status: Any = "error"
            try:
                records = await client.fetch_events(
                    context=self.configuration.context,
                    domain=domain,
                    start_date=start,
                    end_date=end,
                )
                status = 200
            except Exception as e:
                status = getattr(e, "status", None) or "error"
                api_requests.labels(intake_key=intake_key, endpoint="events", status_code=str(status)).inc()
                self.log_exception(e, message=f"Error while fetching Balise events for domain={domain}")
                continue
            finally:
                dt = datetime.now().timestamp() - t0
                api_request_duration.labels(intake_key=intake_key).observe(dt)

            api_requests.labels(intake_key=intake_key, endpoint="events", status_code=str(status)).inc()

            if not records:
                continue

            events_collected.labels(intake_key=intake_key).inc(len(records))

            batch: List[Dict[str, Any]] = []
            for ev in records:
                if not isinstance(ev, dict):
                    continue

                key = self._compute_dedup_key(domain, ev)
                if not self._is_new_event(key):
                    continue

                ev = dict(ev)
                ev["_searched_domain"] = domain
                ev["_context"] = self.configuration.context

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

        if max_seen_ts:
            self.save_checkpoint(max_seen_ts + timedelta(seconds=1))

    async def next_batch(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        cfg = self.module.configuration
        async with AnozrwayClient(
            base_url=cfg.anozrway_base_url,
            token_url=cfg.anozrway_token_url,
            client_id=cfg.anozrway_client_id,
            client_secret=cfg.anozrway_client_secret,
            x_restrict_access=cfg.anozrway_x_restrict_access_token,
            timeout_seconds=cfg.timeout_seconds,
            trigger=self,
        ) as client:
            async for batch in self.fetch_events(client):
                yield batch

    def run(self) -> None:  # pragma: no cover
        import asyncio
        import signal

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def handle_stop_signal() -> None:
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

    async def _async_run(self) -> None:
        intake_key = self.configuration.intake_key
        while self.running:
            try:
                batch_count = 0
                async for batch in self.next_batch():
                    batch_count += 1
                    self.log(message=f"Pushing batch {batch_count} to intake - Events: {len(batch)}", level="info")
                    serialized = [orjson.dumps(ev).decode("utf-8") for ev in batch]
                    await self.push_data_to_intakes(events=serialized)
                    events_forwarded.labels(intake_key=intake_key).inc(len(batch))

                await sleep(int(self.configuration.frequency))
            except AnozrwayAuthError:
                raise
            except Exception as e:
                self.log_exception(e, message="Error in collection loop - retry in 60s")
                await sleep(60)
