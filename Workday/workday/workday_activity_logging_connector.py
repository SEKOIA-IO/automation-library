from sekoia_automation.connector import DefaultConnectorConfiguration
from asyncio import sleep
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Dict, Any, List
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.storage import PersistentJSON
from workday.client.http_client import WorkdayClient
from workday.client.errors import WorkdayAuthError


class WorkdayActivityLoggingConfiguration(DefaultConnectorConfiguration):
    """Connector-specific configuration"""

    frequency: int = 600  # 10 minutes
    chunk_size: int = 1000
    limit: int = 1000  # API max per request


class WorkdayActivityLoggingConnector(AsyncConnector):
    """
    Connector to fetch activity logs from Workday Activity Logging API
    """

    name = "WorkdayActivityLogging"
    configuration: WorkdayActivityLoggingConfiguration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # persistent checkpoint store
        self.context = PersistentJSON("context.json", self._data_path)
        # persistent event cache store (key -> iso timestamp)
        self.event_cache_store = PersistentJSON("event_cache.json", self._data_path)
        self.event_cache_ttl = timedelta(hours=48)

    def last_event_date(self) -> datetime:
        """
        Get the last event date from checkpoint
        If undefined, retrieve events from the last 24 hours
        """
        one_day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        with self.context as c:
            ts = c.get("last_collection_end_time")
            if ts:
                # stored values use 'Z' as UTC marker; normalize to timezone-aware UTC
                return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
        return one_day_ago

    def save_checkpoint(self, last_event_date: datetime):
        """Save checkpoint to persistent storage"""
        with self.context as c:
            # store UTC timestamp with Z suffix
            c["last_collection_end_time"] = last_event_date.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            c["last_successful_run"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _cleanup_event_cache(self):
        """Remove events older than TTL from cache"""
        cutoff = datetime.now(timezone.utc) - self.event_cache_ttl
        with self.event_cache_store as s:
            keys = [k for k, v in s.items()]
            for k in keys:
                try:
                    ts = datetime.fromisoformat(s[k].replace("Z", "+00:00")).astimezone(timezone.utc)
                    if ts < cutoff:
                        del s[k]
                except Exception:
                    del s[k]

    def _is_new_event(self, event: Dict[str, Any]) -> bool:
        """
        Check if event is new using persistent cache
        Cache key: {taskId}:{requestTime}
        """
        cache_key = f"{event['taskId']}:{event['requestTime']}"
        with self.event_cache_store as s:
            if cache_key in s:
                return False
            s[cache_key] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return True

    async def fetch_events(self, client: WorkdayClient) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch activity logs from Workday API with pagination
        """
        # Clean up old cache entries at start
        self._cleanup_event_cache()

        from_time = self.last_event_date()
        to_time = datetime.now(timezone.utc) - timedelta(minutes=2)  # 2-minute buffer

        self.log(message=f"Fetching events from {from_time.isoformat()} to {to_time.isoformat()}", level="info")

        offset = 0
        limit = self.configuration.limit
        # FIXED: Add type annotation for batch
        batch: List[Dict[str, Any]] = []

        while True:
            # Fetch page of events
            events = await client.fetch_activity_logs(from_time=from_time, to_time=to_time, limit=limit, offset=offset)

            if not events:
                # No more events, yield remaining batch
                if batch:
                    yield batch
                break

            # Filter new events using cache
            new_events = [event for event in events if self._is_new_event(event)]

            if new_events:
                batch.extend(new_events)

                # Yield batch when chunk_size is reached
                if len(batch) >= self.configuration.chunk_size:
                    yield batch[: self.configuration.chunk_size]
                    batch = batch[self.configuration.chunk_size :]

            # Check if more pages exist
            if len(events) < limit:
                # Last page, yield remaining batch
                if batch:
                    yield batch
                break

            # Move to next page
            offset += limit

        # Update checkpoint
        self.save_checkpoint(to_time)

    async def next_batch(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Get next batch of events
        Called by AsyncConnector framework
        """
        async with WorkdayClient(
            workday_host=self.module.configuration.workday_host,
            tenant_name=self.module.configuration.tenant_name,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
            refresh_token=self.module.configuration.refresh_token,
        ) as client:
            async for batch in self.fetch_events(client):
                yield batch

    async def run(self):
        """
        Main execution loop
        """
        while self.running:
            try:
                async for batch in self.next_batch():
                    # Push events to intake
                    await self.push_data_to_intakes(events=batch)

                    self.log(message=f"Forwarded {len(batch)} events to intake", level="info")

                # Wait for next polling interval
                await sleep(self.configuration.frequency)

            except WorkdayAuthError as e:
                self.log_exception(e, message="Authentication failed. Check credentials.")
                # Critical error, stop connector
                break

            except Exception as e:
                self.log_exception(e, message="Failed to fetch events")
                # Wait before retry
                await sleep(60)

        self.log(message="Connector stopped", level="info")
