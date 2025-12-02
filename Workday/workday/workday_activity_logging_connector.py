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
        
        self.log(
            message=f"WorkdayActivityLoggingConnector initialized - "
                    f"Data path: {self._data_path}, "
                    f"Frequency: {self.configuration.frequency}s, "
                    f"Chunk size: {self.configuration.chunk_size}, "
                    f"Limit: {self.configuration.limit}",
            level="info"
        )

    def last_event_date(self) -> datetime:
        """
        Get the last event date from checkpoint
        If undefined, retrieve events from the last 24 hours
        """
        one_day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        
        with self.context as c:
            self.log(
                message=f"Reading checkpoint from context - Available keys: {list(c.keys())}",
                level="debug"
            )
            
            ts = c.get("last_collection_end_time")
            if ts:
                last_date = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
                self.log(
                    message=f"Checkpoint found - Last collection end time: {ts} ({last_date.isoformat()})",
                    level="info"
                )
                return last_date
            
            self.log(
                message=f"No checkpoint found - Using default start time: {one_day_ago.isoformat()} (24h ago)",
                level="info"
            )
        
        return one_day_ago

    def save_checkpoint(self, last_event_date: datetime):
        """Save checkpoint to persistent storage"""
        checkpoint_time = last_event_date.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        run_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        with self.context as c:
            c["last_collection_end_time"] = checkpoint_time
            c["last_successful_run"] = run_time
            
        self.log(
            message=f"Checkpoint saved - Last collection end time: {checkpoint_time}, "
                    f"Last successful run: {run_time}",
            level="info"
        )

    def _cleanup_event_cache(self):
        """Remove events older than TTL from cache"""
        cutoff = datetime.now(timezone.utc) - self.event_cache_ttl
        
        self.log(
            message=f"Starting event cache cleanup - Cutoff time: {cutoff.isoformat()} "
                    f"(TTL: {self.event_cache_ttl})",
            level="debug"
        )
        
        with self.event_cache_store as s:
            initial_count = len(s)
            keys = [k for k, v in s.items()]
            removed_count = 0
            
            for k in keys:
                try:
                    ts = datetime.fromisoformat(s[k].replace("Z", "+00:00")).astimezone(timezone.utc)
                    if ts < cutoff:
                        del s[k]
                        removed_count += 1
                except Exception as e:
                    self.log(
                        message=f"Error parsing cache timestamp for key '{k}': {e} - Removing entry",
                        level="warning"
                    )
                    del s[k]
                    removed_count += 1
            
            final_count = len(s)
            self.log(
                message=f"Event cache cleanup complete - "
                        f"Initial: {initial_count}, Removed: {removed_count}, Remaining: {final_count}",
                level="info"
            )

    def _is_new_event(self, event: Dict[str, Any]) -> bool:
        """
        Check if event is new using persistent cache
        Cache key: {taskId}:{requestTime}
        """
        task_id = event.get('taskId', 'unknown')
        request_time = event.get('requestTime', 'unknown')
        cache_key = f"{task_id}:{request_time}"
        
        with self.event_cache_store as s:
            if cache_key in s:
                self.log(
                    message=f"Duplicate event detected - Cache key: {cache_key}",
                    level="debug"
                )
                return False
            
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            s[cache_key] = timestamp
            
            self.log(
                message=f"New event cached - Key: {cache_key}, Timestamp: {timestamp}",
                level="debug"
            )
        
        return True

    async def fetch_events(self, client: WorkdayClient) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch activity logs from Workday API with pagination
        """
        self.log(message="Starting event fetch cycle", level="info")
        
        # Clean up old cache entries at start
        self._cleanup_event_cache()

        from_time = self.last_event_date()
        to_time = datetime.now(timezone.utc) - timedelta(minutes=2)  # 2-minute buffer

        self.log(
            message=f"Fetch parameters - From: {from_time.isoformat()}, "
                    f"To: {to_time.isoformat()}, "
                    f"Time window: {(to_time - from_time).total_seconds() / 60:.1f} minutes",
            level="info"
        )

        offset = 0
        limit = self.configuration.limit
        batch: List[Dict[str, Any]] = []
        total_events_fetched = 0
        total_new_events = 0
        total_duplicate_events = 0
        page_count = 0

        while True:
            page_count += 1
            self.log(
                message=f"Fetching page {page_count} - Offset: {offset}, Limit: {limit}",
                level="info"
            )
            
            # Fetch page of events
            try:
                events = await client.fetch_activity_logs(
                    from_time=from_time, to_time=to_time, limit=limit, offset=offset
                )
                
                events_received = len(events) if events else 0
                total_events_fetched += events_received
                
                self.log(
                    message=f"Page {page_count} received - Events: {events_received}",
                    level="info"
                )
                
                if events_received > 0:
                    self.log(
                        message=f"Sample event from page {page_count}: {events[0] if events else 'None'}",
                        level="debug"
                    )
                
            except Exception as e:
                self.log(
                    message=f"Error fetching page {page_count} at offset {offset}: {e}",
                    level="error"
                )
                raise

            if not events:
                self.log(
                    message=f"No more events - Total pages: {page_count}, "
                            f"Total events fetched: {total_events_fetched}",
                    level="info"
                )
                
                # No more events, yield remaining batch
                if batch:
                    self.log(
                        message=f"Yielding final batch - Events: {len(batch)}",
                        level="info"
                    )
                    yield batch
                break

            # Filter new events using cache
            new_events = [event for event in events if self._is_new_event(event)]
            duplicate_count = len(events) - len(new_events)
            total_new_events += len(new_events)
            total_duplicate_events += duplicate_count
            
            self.log(
                message=f"Page {page_count} filtering - "
                        f"New: {len(new_events)}, Duplicates: {duplicate_count}",
                level="info"
            )

            if new_events:
                batch.extend(new_events)
                self.log(
                    message=f"Batch updated - Current batch size: {len(batch)}, "
                            f"Chunk size threshold: {self.configuration.chunk_size}",
                    level="debug"
                )

                # Yield batch when chunk_size is reached
                if len(batch) >= self.configuration.chunk_size:
                    chunk = batch[: self.configuration.chunk_size]
                    batch = batch[self.configuration.chunk_size :]
                    
                    self.log(
                        message=f"Chunk size reached - Yielding {len(chunk)} events, "
                                f"Remaining in batch: {len(batch)}",
                        level="info"
                    )
                    yield chunk

            # Check if more pages exist
            if len(events) < limit:
                self.log(
                    message=f"Last page detected - Events received ({len(events)}) < Limit ({limit})",
                    level="info"
                )
                
                # Last page, yield remaining batch
                if batch:
                    self.log(
                        message=f"Yielding remaining batch - Events: {len(batch)}",
                        level="info"
                    )
                    yield batch
                break

            # Move to next page
            offset += limit
            self.log(
                message=f"Moving to next page - New offset: {offset}",
                level="debug"
            )

        # Update checkpoint
        self.save_checkpoint(to_time)
        
        self.log(
            message=f"Fetch cycle complete - "
                    f"Total pages: {page_count}, "
                    f"Total events fetched: {total_events_fetched}, "
                    f"New events: {total_new_events}, "
                    f"Duplicates filtered: {total_duplicate_events}",
            level="info"
        )

    async def next_batch(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Get next batch of events
        Called by AsyncConnector framework
        """
        self.log(
            message=f"Creating WorkdayClient - "
                    f"Host: {self.module.configuration.workday_host}, "
                    f"Tenant: {self.module.configuration.tenant_name}, "
                    f"Client ID: {self.module.configuration.client_id[:8]}...",
            level="info"
        )
        
        async with WorkdayClient(
            workday_host=self.module.configuration.workday_host,
            tenant_name=self.module.configuration.tenant_name,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
            refresh_token=self.module.configuration.refresh_token,
            logger=self.log  # Pass the Sekoia logger
        ) as client:
            self.log(message="WorkdayClient context entered successfully", level="info")
            
            async for batch in self.fetch_events(client):
                self.log(
                    message=f"Batch ready for intake - Events: {len(batch)}",
                    level="info"
                )
                yield batch

    async def run(self):
        """
        Main execution loop
        """
        self.log(
            message=f"Connector starting - Polling frequency: {self.configuration.frequency}s",
            level="info"
        )
        
        iteration = 0
        
        while self.running:
            iteration += 1
            self.log(
                message=f"=== Starting iteration {iteration} ===",
                level="info"
            )
            
            try:
                batch_count = 0
                total_events = 0
                
                async for batch in self.next_batch():
                    batch_count += 1
                    batch_size = len(batch)
                    total_events += batch_size
                    
                    self.log(
                        message=f"Pushing batch {batch_count} to intake - Events: {batch_size}",
                        level="info"
                    )
                    
                    # Push events to intake
                    try:
                        await self.push_data_to_intakes(events=batch)
                        self.log(
                            message=f"Batch {batch_count} successfully forwarded to intake ({batch_size} events)",
                            level="info"
                        )
                    except Exception as e:
                        self.log(
                            message=f"Failed to push batch {batch_count} to intake: {e}",
                            level="error"
                        )
                        raise

                self.log(
                    message=f"Iteration {iteration} complete - "
                            f"Total batches: {batch_count}, Total events: {total_events}",
                    level="info"
                )

                # Wait for next polling interval
                self.log(
                    message=f"Sleeping for {self.configuration.frequency}s until next iteration",
                    level="info"
                )
                await sleep(self.configuration.frequency)

            except WorkdayAuthError as e:
                self.log_exception(e, message="CRITICAL: Authentication failed - Check credentials")
                self.log(
                    message="Stopping connector due to authentication failure",
                    level="error"
                )
                # Critical error, stop connector
                break

            except Exception as e:
                self.log_exception(
                    e, 
                    message=f"Error in iteration {iteration} - Will retry in 60s"
                )
                # Wait before retry
                await sleep(60)

        self.log(message="Connector stopped gracefully", level="info")