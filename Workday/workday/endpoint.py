import time
import shelve
from threading import Event, Lock, Thread
from functools import cached_property
from datetime import datetime, timezone, timedelta
from dateutil.parser import isoparse
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import Connector

import orjson
from .client import WorkdayApiClient


class WorkdayEndpoint(Thread):
    METHOD_URI = "/ccx/api/privacy/v1/{tenant}/activityLogging"
    FEATURE_NAME = "activityLogging"

    def __init__(self, connector: Connector):
        super().__init__()
        self._stop_event = Event()
        self.name = self.FEATURE_NAME
        self.connector = connector

        self.cursor = CheckpointDatetime(
            path=self.connector.data_path,
            start_at=timedelta(hours=1),
            ignore_older_than=timedelta(days=7),
            subkey=self.name,
            lock=self.connector.context_lock,
        )
        self.from_date = self.cursor.offset
        self._cache_path = str(self.connector.data_path / f"workday_dedup_{self.name}.db")
        self._cache_lock = Lock()

        self.chunk_size = 1000
        self.instances_returned = 1
        self.rate_limit_delay = 0.1  # 100ms between requests

    def log(self, *args, **kwargs):
        self.connector.log(*args, **kwargs)

    @cached_property
    def client(self) -> WorkdayApiClient:
        cfg = self.connector.module.configuration
        return WorkdayApiClient(
            token_endpoint=cfg.token_endpoint,
            client_id=cfg.client_id,
            client_secret=cfg.client_secret,
            refresh_token=cfg.refresh_token,
            workday_host=cfg.workday_host,
        )

    def enrich_event(self, event: dict) -> dict:
        event["sekoia_event_type"] = self.FEATURE_NAME
        return event

    def extract_timestamp(self, event: dict) -> datetime:
        return isoparse(event["requestTime"])

    def _cache_key(self, event: dict) -> str:
        return f"{event.get('taskId')}:{event.get('requestTime')}"

    def _is_duplicate(self, key: str) -> bool:
        with self._cache_lock, shelve.open(self._cache_path) as db:
            return key in db

    def _add_cache(self, key: str, ttl_seconds: int = 48*3600):
        expiry = int(time.time()) + ttl_seconds
        with self._cache_lock, shelve.open(self._cache_path) as db:
            db[key] = expiry

    def _cleanup_cache(self):
        now = int(time.time())
        with self._cache_lock, shelve.open(self._cache_path) as db:
            keys_to_delete = [k for k, v in db.items() if v < now]
            for k in keys_to_delete:
                del db[k]

    def _fetch_page(self, from_ts: str, to_ts: str, offset: int) -> list:
        url = f"https://{self.client.workday_host}/ccx/api/privacy/v1/{self.connector.module.configuration.tenant_name}/activityLogging"
        params = {
            "from": from_ts,
            "to": to_ts,
            "limit": self.chunk_size,
            "offset": offset,
            "instancesReturned": self.instances_returned,
        }

        while self._stop_event.is_set() is False:
            resp = self.client.get(url, params=params)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 1))
                self.log(message=f"Rate limit exceeded, sleeping {retry_after}s", level="warning")
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            return resp.json()
        return []

    def fetch_events(self):
        self._cleanup_cache()
        most_recent_date_seen = self.from_date
        to_date = datetime.now(timezone.utc) - timedelta(minutes=2)
        from_ts = most_recent_date_seen.isoformat()
        to_ts = to_date.isoformat()
        offset = 0

        while True:
            page = self._fetch_page(from_ts, to_ts, offset)
            if not page:
                break

            events = []
            for event in page:
                key = self._cache_key(event)
                if not self._is_duplicate(key):
                    self._add_cache(key)
                    events.append(self.enrich_event(event))

            if events:
                last_event_dt = max(self.extract_timestamp(e) for e in events)
                if last_event_dt > most_recent_date_seen:
                    most_recent_date_seen = last_event_dt + timedelta(microseconds=1)

            yield events

            if len(page) < self.chunk_size:
                break
            offset += self.chunk_size
            time.sleep(self.rate_limit_delay)

        self.cursor.offset = most_recent_date_seen
        self.from_date = most_recent_date_seen

    def next_batch(self):
        batch_start = time.time()
        for events in self.fetch_events():
            batch_to_send = [orjson.dumps(e).decode() for e in events]
            if batch_to_send:
                self.connector.push_events_to_intakes(batch_to_send)
                self.log(f"Forwarded {len(batch_to_send)} events", level="info")
        batch_end = time.time()
        sleep_time = max(0, self.connector.configuration.frequency - (batch_end - batch_start))
        if sleep_time > 0:
            time.sleep(sleep_time)

    def run(self):
        while not self._stop_event.is_set():
            self.next_batch()

    def stop(self):
        self._stop_event.set()
