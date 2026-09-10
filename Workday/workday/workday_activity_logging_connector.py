from sekoia_automation.connector import DefaultConnectorConfiguration
from asyncio import sleep
from cachetools import LRUCache
from loguru import logger
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Dict, Any, List, Optional
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.storage import PersistentJSON
from workday.client.http_client import WorkdayClient
from workday.client.errors import WorkdayAuthError
from workday.metrics import (
    CHECKPOINT_AGE,
    EVENTS_DUPLICATED,
    EVENTS_LAG,
    EVENTS_TRUNCATED,
    FORWARD_EVENTS_DURATION,
    OUTCOMING_EVENTS,
)
import asyncio
import signal
import time

# Internal tuning constants. These are deliberately NOT connector settings: they cannot be chosen
# meaningfully without knowing the connector's internals, and a wrong value reintroduces the very
# problems they guard against (an oversized cache throttles collection, an oversized window is
# silently truncated by the API). Saturation is reported through EVENTS_TRUNCATED and EVENTS_LAG,
# so operators get a signal instead of a knob.

# Cap on a single collection window, so a late checkpoint catches up gradually instead of asking
# for a gap larger than the instancesReturned pool.
MAX_WINDOW_MINUTES = 60

# Bounded dedup cache. Windows do not overlap, so it only has to cover events straddling a window
# edge; the bound is what keeps deduplication at a constant cost whatever the volume collected.
EVENT_CACHE_SIZE = 100_000

# Attempts on a single page before the cycle is aborted and retried from the same checkpoint.
MAX_PAGE_ATTEMPTS = 5

# Above this length a log message is truncated (see `log`). The intake answers a rejected chunk
# with one error object per event, so a refused 1,000-event chunk yields a ~90,000 character line
# that is unreadable in the GUI and repeats the same error a thousand times. 2,000 characters keep
# the SDK's prefix plus enough of the body to identify the cause.
MAX_LOG_MESSAGE_CHARS = 2000

# Logging convention, aligned with the rest of the automation library (Trellix, Broadcom, Checkpoint):
#   self.log(...)  -> customer-visible in the platform GUI. Reserved for the cycle outcome, states
#                     the operator can act on (lag, backlog, truncation) and errors. A handful of
#                     lines per cycle at most.
#   logger.*(...)  -> pod stdout only (Loki). Pagination, batching and client internals live here:
#                     useful when debugging, noise for the customer.
# Two reasons not to push the internals through self.log: they drown the actionable lines, and the
# SDK drops any log line whose exact text repeats within 60s, so constant-text mechanics silently
# evict nothing while still costing an API round-trip.


class WorkdayActivityLoggingConfiguration(DefaultConnectorConfiguration):
    """Connector-specific configuration"""

    frequency: int = 600  # 10 minutes
    chunk_size: int = 1000
    limit: int = 1000  # API max per request
    instances_returned: int = 1  # pool size in units of 10,000 (1..25); 1 = 10,000 records (most performant)
    intake_server: Optional[str] = None
    intake_key: str = ""


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
        # persistent event cache store, holding the dedup keys of the most recent events
        self.event_cache_store = PersistentJSON("event_cache.json", self._data_path)
        # set by fetch_events: True while the checkpoint is behind and windows are being capped
        self._window_was_capped = False
        # set by fetch_events: seconds behind real time at the end of the last completed cycle
        self._last_lag: Optional[float] = None

        # Dedup cache held in memory and bounded by construction. It used to be an unbounded dict
        # rewritten to disk on every single event, which made collection slower as it grew and
        # ultimately throttled it below the tenant's real event rate. An LRU cache cannot grow past
        # EVENT_CACHE_SIZE, so the cost of deduplication stays flat no matter the volume.
        self.events_cache: LRUCache = self._load_events_cache()

        self.log(
            message=f"WorkdayActivityLoggingConnector initialized - "
            f"Data path: {self._data_path}, "
            f"Frequency: {self.configuration.frequency}s, "
            f"Chunk size: {self.configuration.chunk_size}, "
            f"Limit: {self.configuration.limit}",
            level="info",
        )

    def log(self, message: str, level: str = "info", *args, **kwargs) -> None:
        """Cap oversized log messages before they reach the platform.

        The batch API answers a rejected chunk with one error object per event, so a rejected
        1,000-event chunk produces a ~90,000 character line repeating the same error a thousand
        times. The SDK forwards that body verbatim from `_async_send_chunk`, which cannot be
        overridden, so the cap is applied here -- the last point of control before the API call.
        Neither the SDK nor any other connector provides this, hence the local override.
        """
        if len(message) > MAX_LOG_MESSAGE_CHARS:
            message = f"{message[:MAX_LOG_MESSAGE_CHARS]}... [truncated, {len(message)} chars total]"
        super().log(message, level, *args, **kwargs)  # type: ignore[arg-type]

    def last_event_date(self) -> datetime:
        """
        Get the last event date from checkpoint
        If undefined, retrieve events from the last 24 hours
        """
        one_day_ago = datetime.now(timezone.utc) - timedelta(hours=24)

        with self.context as c:
            logger.debug("Reading checkpoint from context - Available keys: {keys}", keys=list(c.keys()))

            ts = c.get("last_collection_end_time")
            if ts:
                last_date = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
                CHECKPOINT_AGE.labels(intake_key=self.configuration.intake_key).set(
                    (datetime.now(timezone.utc) - last_date).total_seconds()
                )
                logger.info(
                    "Checkpoint found - Last collection end time: {ts} ({parsed})",
                    ts=ts,
                    parsed=last_date.isoformat(),
                )
                return last_date

            self.log(
                message=f"No checkpoint found - Using default start time: {one_day_ago.isoformat()} (24h ago)",
                level="info",
            )

        return one_day_ago

    def save_checkpoint(self, last_event_date: datetime):
        """Save checkpoint to persistent storage"""
        checkpoint_time = last_event_date.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        run_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        with self.context as c:
            c["last_collection_end_time"] = checkpoint_time
            c["last_successful_run"] = run_time

        CHECKPOINT_AGE.labels(intake_key=self.configuration.intake_key).set(
            (datetime.now(timezone.utc) - last_event_date.astimezone(timezone.utc)).total_seconds()
        )

        logger.info(
            "Checkpoint saved - Last collection end time: {checkpoint}, Last successful run: {run}",
            checkpoint=checkpoint_time,
            run=run_time,
        )

    def _load_events_cache(self) -> LRUCache:
        """Restore the dedup cache from disk into a bounded LRU cache."""
        cache: LRUCache = LRUCache(maxsize=EVENT_CACHE_SIZE)

        with self.event_cache_store as s:
            if "events_cache" in s:
                cached_keys = list(s["events_cache"])
            else:
                # Cache written by <=0.2.x: dedup keys were stored at the top level, mapped to the
                # timestamp at which they were seen. Keep the most recent ones so an in-place
                # upgrade does not re-forward the last collected window.
                cached_keys = [key for key, _ in sorted(s.items(), key=lambda kv: str(kv[1]))]

        # An LRU keeps the *last* inserted keys, so the tail of the list is what survives eviction.
        for key in cached_keys[-EVENT_CACHE_SIZE:]:
            cache[key] = True

        return cache

    def _save_events_cache(self) -> None:
        """Persist the dedup cache so restarts do not re-forward the events of the last window."""
        with self.event_cache_store as s:
            s["events_cache"] = list(self.events_cache.keys())

    @staticmethod
    def _cache_key(event: Dict[str, Any]) -> str:
        """Build the dedup cache key for an event: {taskId}:{requestTime}"""
        return f"{event.get('taskId', 'unknown')}:{event.get('requestTime', 'unknown')}"

    def _filter_new_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out events already seen, and remember the new ones.

        Purely in-memory: the cache is loaded once at startup and persisted once per cycle. The
        0.2.x implementation opened a PersistentJSON context per event, and leaving that context
        rewrites the whole cache file -- at ~490,000 entries that measured ~0.38s per event in
        production (~6 minutes per 1,000-event page), throttling collection below the tenant's real
        event rate.
        """
        new_events: List[Dict[str, Any]] = []

        for event in events:
            cache_key = self._cache_key(event)
            if cache_key in self.events_cache:
                continue

            self.events_cache[cache_key] = True
            new_events.append(event)

        return new_events

    def _is_new_event(self, event: Dict[str, Any]) -> bool:
        """Check whether a single event has not been collected yet."""
        return bool(self._filter_new_events([event]))

    async def fetch_events(self, client: WorkdayClient) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch activity logs from Workday API with pagination
        """
        logger.info("Starting event fetch cycle")

        from_time = self.last_event_date()
        to_time = datetime.now(timezone.utc) - timedelta(minutes=2)  # 2-minute buffer

        # NOTE: the checkpoint is intentionally saved at the END of this cycle (after every page has
        # been fetched and yielded), so an interrupted or truncated collection never advances past
        # events that were not actually collected.

        # Cap the window. When the checkpoint is far behind (after an outage or a slow-collection
        # backlog), asking for the whole gap at once would exceed the instancesReturned pool and be
        # silently truncated. Collecting one bounded slice per cycle lets the connector walk the
        # backlog forward without losing the surplus.
        max_window = timedelta(minutes=MAX_WINDOW_MINUTES)
        capped = False
        if to_time - from_time > max_window:
            to_time = from_time + max_window
            capped = True
        self._window_was_capped = capped

        logger.info(
            "Fetch parameters - From: {from_time}, To: {to_time}, Time window: {window:.1f} minutes",
            from_time=from_time.isoformat(),
            to_time=to_time.isoformat(),
            window=(to_time - from_time).total_seconds() / 60,
        )

        if capped:
            backlog = datetime.now(timezone.utc) - timedelta(minutes=2) - to_time
            self.log(
                message=(
                    f"Collection window capped at {MAX_WINDOW_MINUTES} minutes - "
                    f"still {backlog.total_seconds() / 60:.1f} minutes behind real time; "
                    f"the backlog is caught up one window per cycle."
                ),
                level="info",
            )

        offset = 0
        limit = self.configuration.limit
        batch: List[Dict[str, Any]] = []
        total_events_fetched = 0
        total_new_events = 0
        total_duplicate_events = 0
        page_count = 0

        page_attempts = 0

        while True:
            if page_attempts == 0:
                page_count += 1
                logger.info(
                    "Fetching page {page} - Offset: {offset}, Limit: {limit}",
                    page=page_count,
                    offset=offset,
                    limit=limit,
                )

            try:
                events = await client.fetch_activity_logs(
                    from_time=from_time,
                    to_time=to_time,
                    limit=limit,
                    offset=offset,
                    instances_returned=self.configuration.instances_returned,
                )

                events_received = len(events) if events else 0
                total_events_fetched += events_received
                page_attempts = 0

                logger.info("Page {page} received - Events: {count}", page=page_count, count=events_received)

            except Exception as e:
                # Bounded retry. An unbounded `continue` here used to spin forever on a durably
                # failing page, never advancing the checkpoint and never surfacing a fatal error.
                page_attempts += 1
                if page_attempts >= MAX_PAGE_ATTEMPTS:
                    self.log(
                        message=(
                            f"Page {page_count} at offset {offset} failed "
                            f"{page_attempts} times, aborting this cycle: {e}"
                        ),
                        level="error",
                    )
                    # Flush what was already collected so the successful pages are not discarded,
                    # then abort WITHOUT saving the checkpoint: the window is retried in full next
                    # cycle rather than silently skipping the events we could not fetch.
                    if batch:
                        yield batch
                    return

                backoff = 2**page_attempts
                self.log(
                    message=(
                        f"Transient error fetching page {page_count} at offset {offset} "
                        f"(attempt {page_attempts}/{MAX_PAGE_ATTEMPTS}), "
                        f"retrying in {backoff}s: {e}"
                    ),
                    level="warning",
                )
                await asyncio.sleep(backoff)
                continue

            if not events:
                logger.info(
                    "No more events - Total pages: {pages}, Total events fetched: {total}",
                    pages=page_count,
                    total=total_events_fetched,
                )

                if batch:
                    logger.debug("Yielding final batch - Events: {count}", count=len(batch))
                    yield batch
                break

            new_events = self._filter_new_events(events)
            duplicate_count = len(events) - len(new_events)
            total_new_events += len(new_events)
            total_duplicate_events += duplicate_count
            if duplicate_count:
                EVENTS_DUPLICATED.labels(intake_key=self.configuration.intake_key).inc(duplicate_count)

            logger.info(
                "Page {page} filtering - New: {new}, Duplicates: {dupes}",
                page=page_count,
                new=len(new_events),
                dupes=duplicate_count,
            )

            if new_events:
                batch.extend(new_events)
                logger.debug(
                    "Batch updated - Current batch size: {size}, Chunk size threshold: {threshold}",
                    size=len(batch),
                    threshold=self.configuration.chunk_size,
                )

                if len(batch) >= self.configuration.chunk_size:
                    chunk = batch[: self.configuration.chunk_size]
                    batch = batch[self.configuration.chunk_size :]
                    logger.debug(
                        "Chunk size reached - Yielding {yielded} events, Remaining in batch: {remaining}",
                        yielded=len(chunk),
                        remaining=len(batch),
                    )
                    yield chunk

            if len(events) < limit:
                logger.info(
                    "Last page detected - Events received ({received}) < Limit ({limit})",
                    received=len(events),
                    limit=limit,
                )

                if batch:
                    logger.debug("Yielding remaining batch - Events: {count}", count=len(batch))
                    yield batch
                break

            offset += limit
            logger.debug("Moving to next page - New offset: {offset}", offset=offset)

        logger.info(
            "Fetch cycle complete - Total pages: {pages}, Total events fetched: {fetched}, "
            "New events: {new}, Duplicates filtered: {dupes}",
            pages=page_count,
            fetched=total_events_fetched,
            new=total_new_events,
            dupes=total_duplicate_events,
        )

        # Detect window saturation: if we paged through the whole instancesReturned pool, the API may
        # have truncated extra events for this window -> surface it instead of failing silently.
        pool_size = self.configuration.instances_returned * 10000
        if total_events_fetched >= pool_size:
            EVENTS_TRUNCATED.labels(intake_key=self.configuration.intake_key).inc()
            self.log(
                message=(
                    f"Activity window {from_time.isoformat()} -> {to_time.isoformat()} reached the "
                    f"instancesReturned pool ({pool_size} records); some events may have been truncated. "
                    f"Increase 'instances_returned' (max 25) or lower 'frequency' to shorten the window."
                ),
                level="warning",
            )

        # Advance the checkpoint only now that the full window has been fetched and yielded.
        self.save_checkpoint(to_time)
        # Persist the dedup cache once per cycle so a restart does not re-forward the last window.
        self._save_events_cache()

        # Report how far behind real time the collection is. This is the standard signal used across
        # the automation library to tell "collecting slowly" from "collecting everything": a lag that
        # keeps growing means the connector is not keeping up with the tenant's event rate.
        # The value is surfaced to the customer once per cycle by `_lag_summary`.
        self._last_lag = (datetime.now(timezone.utc) - to_time).total_seconds()
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(self._last_lag)
        logger.info("Collection lag: {lag:.0f}s behind real time", lag=self._last_lag)

    def _lag_summary(self) -> str:
        """Render the collection lag for the per-cycle customer-facing summary."""
        lag = self._last_lag
        if lag is None:
            return "collection lag unknown"
        if lag < 120:
            return "up to date"
        if self._window_was_capped:
            return f"catching up, {lag / 60:.0f} min behind real time"
        return f"{lag / 60:.0f} min behind real time"

    async def next_batch(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Get next batch of events
        Called by AsyncConnector framework
        """
        logger.info(
            "Creating WorkdayClient - Host: {host}, Tenant: {tenant}, Client ID: {client_id}...",
            host=self.module.configuration.workday_host,
            tenant=self.module.configuration.tenant_name,
            client_id=self.module.configuration.client_id[:8],
        )

        async with WorkdayClient(
            workday_host=self.module.configuration.workday_host,
            tenant_name=self.module.configuration.tenant_name,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
            refresh_token=self.module.configuration.refresh_token,
            intake_key=self.configuration.intake_key,
        ) as client:
            logger.debug("WorkdayClient context entered successfully")

            async for batch in self.fetch_events(client):
                logger.debug("Batch ready for intake - Events: {count}", count=len(batch))
                yield batch

    def run(self):
        """
        Main execution loop
        Runs the async event collection in a synchronous wrapper
        """
        self.log(message=f"Connector starting - Polling frequency: {self.configuration.frequency}s", level="info")

        loop = asyncio.get_event_loop()

        def handle_stop_signal():
            self.log(message="Received stop signal", level="info")
            loop.create_task(self.shutdown())

        loop.add_signal_handler(signal.SIGTERM, handle_stop_signal)
        loop.add_signal_handler(signal.SIGINT, handle_stop_signal)

        try:
            loop.run_until_complete(self._async_run())
        except WorkdayAuthError as e:
            self.log_exception(e, message="CRITICAL: Authentication failed - Check credentials")
            self.log(message="Stopping connector due to authentication failure", level="error")
        except Exception as e:
            self.log_exception(e, message="Unexpected error in connector execution")
        finally:
            loop.close()

        self.log(message="Connector stopped gracefully", level="info")

    async def _async_run(self):
        """
        Internal async execution loop
        """
        iteration = 0

        while self.running:
            iteration += 1
            logger.info("=== Starting iteration {iteration} ===", iteration=iteration)

            # Mark the connector alive on every cycle. A collection window can legitimately yield no
            # event (or fail), and `_last_events_time` is only refreshed by a successful intake push;
            # without this, a long quiet stretch would look indistinguishable from a hung process.
            self.heartbeat()

            try:
                batch_count = 0
                total_events = 0

                async for batch in self.next_batch():
                    batch_count += 1
                    batch_size = len(batch)
                    total_events += batch_size

                    logger.debug("Pushing batch {n} to intake - Events: {size}", n=batch_count, size=batch_size)

                    try:
                        push_start = time.time()
                        # Trust the event ids returned by the intake, not the size of what we sent:
                        # the SDK's async chunk sender logs HTTP errors instead of raising, so a
                        # rejected batch (e.g. an intake key not propagated yet) comes back as an
                        # empty list rather than an exception. Counting `batch_size` here reported
                        # success for events that were never ingested.
                        pushed_ids = await self.push_data_to_intakes(events=batch)
                        pushed_count = len(pushed_ids)
                        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                            time.time() - push_start
                        )
                        OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(pushed_count)

                        if pushed_count < batch_size:
                            self.log(
                                message=f"Batch {batch_count} was rejected by the intake - "
                                f"{pushed_count}/{batch_size} events accepted. "
                                f"Check the intake key is valid and already provisioned.",
                                level="error",
                            )
                        else:
                            self.log(
                                message=f"Batch {batch_count} successfully forwarded to intake "
                                f"({pushed_count} events)",
                                level="info",
                            )
                    except Exception as e:
                        self.log(message=f"Failed to push batch {batch_count} to intake: {e}", level="error")
                        raise

                # Single customer-visible summary for the whole cycle: what was collected, and
                # whether the connector is keeping up. Everything that led here (pages, batches,
                # offsets) stayed in the pod logs.
                if total_events:
                    outcome = f"Collected {total_events} events in {batch_count} batch(es)"
                else:
                    outcome = "No new events to collect"
                self.log(message=f"{outcome} - {self._lag_summary()}", level="info")

                # While catching up on a backlog the window is capped and the collected slice is
                # already in the past, so waiting a full `frequency` would only widen the gap.
                # Still yield to the event loop rather than spinning straight into the next cycle,
                # so the liveness/metrics servers and the stop signal keep getting scheduled.
                if self._window_was_capped:
                    logger.info("Backlog in progress - starting next iteration immediately")
                    await sleep(1)
                    continue

                logger.info("Sleeping for {frequency}s until next iteration", frequency=self.configuration.frequency)
                await sleep(self.configuration.frequency)

            except WorkdayAuthError:
                raise

            except Exception as e:
                self.log_exception(e, message=f"Error in iteration {iteration} - Will retry in 60s")
                await sleep(60)
