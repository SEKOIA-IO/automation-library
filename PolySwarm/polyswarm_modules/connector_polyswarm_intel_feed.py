"""Scheduled, checkpointed pull of new PolySwarm results into a Sekoia intake.

WHAT THIS MIRRORS

The PolySwarm Splunk app ships a modular input that pulls artifacts on a timer.
This connector is the Sekoia equivalent of that input. It builds the same kind of
Lucene query against the metadata search endpoint, walks the same forward moving
time window, and emits one event per artifact.

WHAT THE API SERVES SERVER SIDE, AND WHAT IT DOES NOT

Everything the operator can filter on here is a server side query argument. The
connector does not pull a wide result set and quietly narrow it afterwards.

  malware family      server side. Each family becomes an OR group over the five
                      fields PolySwarm spreads family attribution across, because
                      no single canonical family field exists on the document.
  tag                 server side, as an exact quoted tag term.
  minimum polyscore   server side, as a range term on scan.latest_scan.polyscore.
  time window         server side, as a range term on artifact.created. This is
                      also the checkpoint, so position and filter are one thing.
  community           server side, sent as its own request parameter.

Two capabilities the Splunk input has cannot be served by the installed
polyswarm-api client, and are therefore NOT implemented rather than faked:

  1. Page size and explicit offset. PolyswarmAPI.search_by_metadata accepts no
     offset or limit argument. The client owns pagination internally: the value
     it returns is a generator that fetches the next page whenever the current
     one is exhausted, driven by the has_more flag in the response envelope. So
     the Splunk input's page_size setting and its hard ceiling on pages per run
     have no equivalent here. What this connector can do, and does, is stop
     consuming the generator, which stops the next page being fetched, because
     the generator is lazy.
  2. Result ordering. The endpoint answers newest first and exposes no sort
     argument. The Splunk input copes with a capped run by recording how far it
     drained and walking backwards through the remainder on later runs. That
     machinery is not ported. Instead this connector bounds the amount of work
     per run by bounding the WINDOW rather than the result count, so catch up
     always moves forward and never skips. The per run event ceiling is a safety
     guard that shrinks the window, and is waived at the smallest window. See
     MAX EVENTS PER RUN below.

A third difference worth stating: the detection counts on an event are the
platform's own aggregate from scan.detections, passed through under the
platform's names. They are not recomputed from the bloom mask of per engine
assertions, because the metadata search response does not carry assertions at
all. An abstaining engine may therefore be counted the way the platform counts
it, which is not necessarily the way a scan result action would count it.

MAX EVENTS PER RUN

A window that would exceed max_events_per_run is not pushed. It is halved and
asked for again, down to MIN_WINDOW_SECONDS. Pushing a partial result and then
re throwing the same window at the intake on the next run would duplicate
events, and advancing the checkpoint past unread artifacts would lose them, so
narrowing the window is the only way to honour the ceiling without either.

At MIN_WINDOW_SECONDS the ceiling is waived and the whole window is pushed. The
alternative, refusing it, cannot be recovered from without an operator: the
window cannot be made smaller, so every later run would ask for the same one
and the feed would stop for good. Pushing it loses nothing, because the
connector consumes the whole result and the checkpoint moves past it, and the
cost is one oversized batch, which the SDK already splits into chunks. The
connector logs a warning when it does so, so an operator can tighten the
filters.

PUSH FAILURES

The SDK's push_events_to_intakes never raises. It retries each chunk, and when a
chunk still fails it logs the failure and leaves that chunk out of the returned
event ids. The connector therefore compares the number of ids with the number
of events and, on a shortfall, leaves the checkpoint and the remembered digests
where they were and backs off. The next attempt asks for the same window again.
Chunks the intake did accept the first time are sent a second time, so delivery
is at least once, which is the safe side of the trade: the alternative is a
window marked done with artifacts in it that never arrived.

CATCH UP PACING

A run that reaches the frontier (now minus lag_seconds) sleeps for the
configured frequency. A run that stops short of it, because the window was
capped at MAX_WINDOW_MINUTES or halved, does not sleep, so a connector that was
down for a day or a month walks forward as fast as the API answers instead of
one slice per frequency.

CHECKPOINTING

Position is the SDK's CheckpointDatetime, stored in context.json under the
connector's data path. It holds the end of the last window that was covered
whole. The setter is monotonic, so a checkpoint never moves backwards.

A Lucene range term is inclusive at both ends, so an artifact created exactly on
a window boundary falls inside two consecutive windows. The connector therefore
also remembers the digests it emitted on the previous run and refuses them a
second time. That list lives in its own file rather than in context.json:
PersistentJSON caches the whole document in memory and rewrites it wholesale, so
two instances pointed at one file would clobber each other's keys.

THE API KEY

It comes from self.module.configuration.apikey and is never logged, never put in
an event, and never interpolated into a message. Failures are reported by
exception class name only. The client's own exception text can embed the request
parameters that produced it, so formatting an exception into a log line is how a
query, and on some code paths a credential, escapes.

ARTIFACTS THAT QUALIFY LATE

The window is cut on artifact.created, the moment PolySwarm first accepted the
artifact. The metadata document carries one other timestamp in the index,
scan.latest_scan.created, and the client exposes it as last_scanned. It was
considered as the window field and rejected. It moves on a rescan only, not when
a sandbox report attributes a family or when a polyscore is recomputed, so it
would still miss the case that matters, and it would hand back the same artifact
every time it is rescanned, which the one run digest list cannot suppress. No
field in the response records when the document last changed, so none is used.
The limitation is documented in the connector description instead: an artifact
whose score or family only qualifies after its window closed is not pulled, and
the way to cover it is a scheduled search action over a longer period.

TIMEZONES

The metadata index is UTC: artifact.created has no offset of its own, and the
query built against it has to line up with that or the window silently drifts.
Every datetime this connector builds itself (the checkpoint, the lag adjusted
frontier, the lookback default) is constructed as an explicitly UTC aware
value, so it only ever needs normalising, never guessing at. A datetime read
back off a PolySwarm API result is a different story: the client does not
always attach a UTC offset to a field the platform itself reports in UTC, so a
naive value can arrive. A naive datetime is assumed to already be UTC rather
than read as the process's local zone, which is what Python's astimezone
would otherwise do to it. See format_window_bound and _as_text.
"""

import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from polyswarm_api import settings as ps_settings
from polyswarm_api.api import PolyswarmAPI
from pydantic import BaseModel, Field
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.client import MISSING_RESULT, build_client
from polyswarm_modules.coerce import NUMERIC_ERRORS, as_names, as_score
from polyswarm_modules.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS

# The Splunk input applies these ceilings and refuses a larger value at save time
# rather than silently correcting it. They are repeated here so the two products
# cannot be configured into disagreeing with each other.
MAX_LOOKBACK_MINUTES = 43200
MAX_LAG_SECONDS = 3600
MAX_EVENTS_PER_RUN = 1000
MAX_SELECTORS = 3

# Highest window a single run will ask for, in minutes. A connector that has been
# down for a week must not ask for a week in one request, and asking for a bounded
# slice per run means catch up always moves forward.
MAX_WINDOW_MINUTES = 360

# How many digests are carried across a run to suppress the inclusive boundary
# duplicate. Results arrive newest first, so the first digests of a run are the
# ones nearest the boundary and the ones worth keeping.
MAX_REMEMBERED_DIGESTS = 1000

# Ceiling on the backoff after repeated API failures.
MAX_BACKOFF_SECONDS = 3600
MIN_WINDOW_SECONDS: int = 60

DIGEST_FILE_NAME = "polyswarm_intel_feed.json"

# Tag pulled when the operator names neither a family nor a tag, so a connector
# left on its defaults collects the curated feed instead of everything.
DEFAULT_SELECTOR_TAG = "feed:premium"

# PolySwarm spreads family attribution across several documents and never
# normalised it into one field, so a family filter has to ask all of them.
FAMILY_FIELDS = (
    "polyunite.malware_family",
    "families",
    "triage_sandbox_v0.analysis.family",
    "cape_sandbox_v2.malware_family",
)
FAMILY_WILDCARD_FIELD = "scan.*.*.metadata.malware_family"

# Bands on the polyscore, not engine verdicts. 0.7 is where the rest of the
# PolySwarm tooling calls an artifact malicious.
MALICIOUS_POLYSCORE = 0.7
SUSPICIOUS_POLYSCORE = 0.4

_LUCENE_SPECIALS = set('+-&|!(){}[]^"~*?:\\/')


def escape_lucene_term(value: str) -> str:
    """Escape a value used as a bare Lucene term.

    Whitespace is removed rather than escaped. A bare term containing a space
    would end the term and turn the rest of the value into a second clause, which
    changes what the query matches instead of failing. An operator who needs a
    value with a space in it has the tag filter, which quotes.
    """
    return "".join(f"\\{char}" if char in _LUCENE_SPECIALS else char for char in value if not char.isspace())


def escape_lucene_phrase(value: str) -> str:
    """Escape a value used inside a quoted Lucene phrase."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def format_polyscore(value: float) -> str:
    """Render a polyscore for a Lucene range term without exponent notation."""
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def format_window_bound(moment: datetime) -> str:
    """Render a window bound the way the metadata index stores artifact.created.

    The index itself is UTC: artifact.created has no offset of its own, so a
    window bound has to be converted to UTC before it is formatted, or the
    query would silently drift by the difference between UTC and whatever
    zone the bound was built in. astimezone requires an aware datetime, which
    is what every caller here passes in (see the TIMEZONES note above).
    """
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")


class IntelFeedConfiguration(DefaultConnectorConfiguration):
    """Operator configuration for one intel feed connector."""

    # DefaultConnectorConfiguration itself defaults this to None. Re-declared
    # here with the platform's own address as the default, matching the
    # descriptor and the convention every connector in the public library
    # uses for this field, so an operator sees a working value rather than
    # an empty one.
    intake_server: str | None = Field(
        default="https://intake.sekoia.io",
        description="Server of the intake server (e.g. 'https://intake.sekoia.io')",
    )
    frequency: int = Field(
        default=900,
        ge=60,
        le=86400,
        description="Seconds between polls",
    )
    families: list[str] = Field(
        default_factory=list,
        description="Malware families to pull, at most three",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags to pull, at most three",
    )
    min_polyscore: float = Field(
        default=0.7,
        gt=0.0,
        le=1.0,
        description="Lowest PolyScore to pull",
    )
    lookback_minutes: int = Field(
        default=1440,
        ge=1,
        le=MAX_LOOKBACK_MINUTES,
        description="How far back the first run reaches",
    )
    lag_seconds: int = Field(
        default=300,
        ge=0,
        le=MAX_LAG_SECONDS,
        description="How far behind the clock each window closes",
    )
    max_events_per_run: int = Field(
        default=200,
        ge=1,
        le=MAX_EVENTS_PER_RUN,
        description="Safety ceiling on the events one run may push",
    )
    community: str | None = Field(
        default=None,
        description="PolySwarm community to pull from, overriding the module setting",
    )


class IntelFeedEvent(BaseModel):
    """One PolySwarm artifact, as it is pushed to the intake."""

    timestamp: str
    sha256: str
    sha1: str = ""
    md5: str = ""
    polyscore: float | None = None
    polyscore_band: str = "unknown"
    malicious_detections: int | None = None
    benign_detections: int | None = None
    total_detections: int | None = None
    families: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    first_seen: str = ""
    last_scanned: str = ""
    mimetype: str = ""
    extended_mimetype: str = ""
    filenames: list[str] = Field(default_factory=list)
    permalink: str = ""
    community: str = ""


def polyscore_band(polyscore: float | None) -> str:
    """Band a polyscore.

    This is a band on the platform's score, not a verdict derived from engine
    assertions, and the two must not be confused. The metadata search response
    carries no assertions, so no assertion derived verdict is available here.
    """
    if polyscore is None:
        return "unknown"
    if polyscore >= MALICIOUS_POLYSCORE:
        return "malicious"
    if polyscore >= SUSPICIOUS_POLYSCORE:
        return "suspicious"
    return "benign"


def _as_text(value: Any) -> str:
    """Render a value as plain text, treating an absent value as empty.

    A datetime read off a PolySwarm API result does not always carry a UTC
    offset: the client can hand back a naive value for a field the platform
    itself always reports in UTC. Calling astimezone on a naive datetime does
    not know that, it reads the naive value as the machine's local zone and
    silently shifts it, which is the recurring bug this guards against. A
    naive value is therefore treated as already being UTC (tzinfo attached,
    nothing shifted), and only a value that already carries an offset is
    normalised with astimezone.
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return aware.astimezone(UTC).isoformat()
    return str(value)


def _as_number(value: Any) -> int | None:
    """Read an integer counter, treating anything unreadable as absent."""
    try:
        return int(value)
    except NUMERIC_ERRORS:
        return None


class IntelFeed(Connector):
    """Pull new PolySwarm artifacts on a schedule and push them to an intake."""

    name = "PolySwarm Intel Feed"

    # The inherited six hours would flag a healthy connector as dead. This one
    # pushes only artifacts that match an operator's family, tag and score
    # filters, and a narrow filter can legitimately match nothing for days. The
    # check is switched off (the SDK treats zero as no limit) because no fixed
    # figure separates a quiet feed from a stuck one.
    #
    # Liveness is answered by the heartbeat instead, which asks the question
    # that actually matters here: is the poll loop still going round. That is
    # true of a healthy feed that happens to be matching nothing, and false of
    # one wedged in a request that never returns, which is the case a restart
    # repairs. The SDK disables the heartbeat check too unless a threshold is
    # set, so last_heartbeat_threshold below turns it back on.
    seconds_without_events = 0

    module: PolyswarmModule
    configuration: IntelFeedConfiguration

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._checkpoint: CheckpointDatetime | None = None
        self._digests: PersistentJSON | None = None
        self._consecutive_failures = 0
        self._api: PolyswarmAPI | None = None

    @property
    def frequency(self) -> int:
        return self.configuration.frequency

    @property
    def last_heartbeat_threshold(self) -> int:  # type: ignore[override]
        """How long without a completed cycle before the platform restarts this.

        Generous on purpose. A cycle ends with a sleep of up to the configured
        frequency, and an hour of back off on top when PolySwarm is unreachable,
        so anything tighter would restart a connector that is merely waiting.
        Read before the configuration is attached, it answers zero, which the
        SDK reads as no check.
        """
        if not getattr(self, "configuration", None):
            return 0
        return max(3 * self.frequency, 2 * MAX_BACKOFF_SECONDS)

    @property
    def checkpoint(self) -> CheckpointDatetime:
        """The SDK checkpoint holding the end of the last window covered whole."""
        if self._checkpoint is None:
            self._checkpoint = CheckpointDatetime(
                path=self.data_path,
                start_at=timedelta(minutes=self.configuration.lookback_minutes),
                ignore_older_than=timedelta(minutes=MAX_LOOKBACK_MINUTES),
            )
        return self._checkpoint

    @property
    def digests(self) -> PersistentJSON:
        """Digests emitted by the previous run, kept out of the checkpoint file."""
        if self._digests is None:
            self._digests = PersistentJSON(DIGEST_FILE_NAME, self.data_path)
        return self._digests

    def client(self) -> PolyswarmAPI:
        """Return the client, building it through the shared factory on first use.

        One client serves every run, so the retrying session and its connection
        pool are reused instead of rebuilt each poll. The key is read when the
        client is built and never leaves this call.
        """
        if self._api is None:
            community = self.configuration.community or self.module.configuration.community
            self._api = build_client(SimpleNamespace(apikey=self.module.configuration.apikey, community=community))
        return self._api

    def build_query(self, window_start: datetime, window_end: datetime) -> str:
        """Build the Lucene query for one window.

        Every operator filter lands in this string or in the community parameter
        that travels beside it. Nothing here is re-applied to the response.
        """
        clauses = [
            f"artifact.created:[{format_window_bound(window_start)} TO {format_window_bound(window_end)}]",
            f"scan.latest_scan.polyscore:>={format_polyscore(self.configuration.min_polyscore)}",
        ]

        selectors: list[str] = []
        for family in self.configuration.families[:MAX_SELECTORS]:
            escaped = escape_lucene_term(family)
            if not escaped:
                continue
            selectors.extend(f"{field}:{escaped}" for field in FAMILY_FIELDS)
            selectors.append(f"{FAMILY_WILDCARD_FIELD}:*{escaped}*")
        for tag in self.configuration.tags[:MAX_SELECTORS]:
            escaped_tag = escape_lucene_phrase(tag.strip())
            if escaped_tag:
                selectors.append(f'tags:"{escaped_tag}"')

        if not selectors:
            selectors.append(f'tags:"{DEFAULT_SELECTOR_TAG}"')

        clauses.append("({})".format(" OR ".join(selectors)))
        return " AND ".join(clauses)

    def window_end(self, window_start: datetime) -> datetime | None:
        """End of the window this run should cover, or None when there is none yet.

        The frontier sits lag_seconds behind the clock so the window does not
        close over artifacts the platform has accepted but not yet indexed. The
        window is capped so a long outage is caught up in bounded slices rather
        than in one unbounded request.

        Built from datetime.now(UTC), explicitly aware, same as window_start,
        which is always the checkpoint's own aware offset. See the TIMEZONES
        note at the top of this file.
        """
        frontier = datetime.now(UTC) - timedelta(seconds=self.configuration.lag_seconds)
        candidate = min(frontier, window_start + timedelta(minutes=MAX_WINDOW_MINUTES))
        if candidate <= window_start:
            return None
        return candidate

    def build_event(self, item: Any) -> IntelFeedEvent | None:
        """Turn one metadata document into an event, or None when it is unreadable.

        An artifact with no readable sha256 has nothing an analyst can pivot on
        and nothing the connector can deduplicate on, so it is dropped rather
        than emitted half formed.
        """
        document: dict[str, Any] = getattr(item, "json", None) or {}
        artifact: dict[str, Any] = document.get("artifact") or {}
        latest_scan: dict[str, Any] = (document.get("scan") or {}).get("latest_scan") or {}
        polyunite: dict[str, Any] = document.get("polyunite") or {}

        sha256 = _as_text(getattr(item, "sha256", "") or artifact.get("sha256", "")).strip()
        if not sha256:
            return None

        polyscore = as_score(getattr(item, "polyscore", None) or latest_scan.get("polyscore"))

        families = as_names(polyunite.get("malware_family")) + as_names(document.get("families"))
        created = _as_text(getattr(item, "created", None))

        return IntelFeedEvent(
            timestamp=created,
            sha256=sha256.lower(),
            sha1=_as_text(getattr(item, "sha1", "")),
            md5=_as_text(getattr(item, "md5", "")),
            polyscore=polyscore,
            polyscore_band=polyscore_band(polyscore),
            malicious_detections=_as_number(getattr(item, "malicious", None)),
            benign_detections=_as_number(getattr(item, "benign", None)),
            total_detections=_as_number(getattr(item, "total_detections", None)),
            families=as_names(families),
            tags=as_names(document.get("tags")),
            first_seen=_as_text(getattr(item, "first_seen", "")),
            last_scanned=_as_text(getattr(item, "last_scanned", "")),
            mimetype=_as_text(getattr(item, "mimetype", "")),
            extended_mimetype=_as_text(getattr(item, "extended_mimetype", "")),
            filenames=as_names(getattr(item, "filenames", None)),
            permalink=f"{ps_settings.DEFAULT_PERMALINK_BASE}/{sha256.lower()}",
            community=_as_text(document.get("community") or document.get("meta_community") or ""),
        )

    def remembered_digests(self) -> set[str]:
        """Digests the previous run emitted, which the boundary would repeat."""
        with self.digests as cache:
            stored = cache.get("emitted_digests") or []
        return {str(digest) for digest in stored}

    def remember_digests(self, digests: list[str]) -> None:
        """Record this run's digests so the next run can refuse the boundary repeat."""
        with self.digests as cache:
            cache["emitted_digests"] = digests[:MAX_REMEMBERED_DIGESTS]

    def results(self, api: PolyswarmAPI, query: str) -> Iterator[Any]:
        """Walk every page of a metadata search.

        The client returns a generator that fetches the next page on demand, so
        pagination happens by consuming this. A 204 or a 404 is the client's way
        of saying there is nothing more, on the first page or any later one, and
        is not an error.
        """
        try:
            yield from api.search_by_metadata(query)
        except MISSING_RESULT:
            return

    def collect(
        self, window_start: datetime, window_end: datetime, enforce_ceiling: bool = True
    ) -> tuple[list[dict[str, Any]], list[str], bool]:
        """Collect one window. Returns the events, their digests, and whether the run was capped.

        With enforce_ceiling off, the whole window is read however many
        artifacts it holds. See MAX EVENTS PER RUN at the top of this file.
        """
        api = self.client()
        query = self.build_query(window_start, window_end)
        already_seen = self.remembered_digests()

        events: list[dict[str, Any]] = []
        digests: list[str] = []
        seen: set[str] = set()
        unreadable = 0

        for item in self.results(api, query):
            event = self.build_event(item)
            if event is None:
                unreadable += 1
                continue
            if event.sha256 in seen or event.sha256 in already_seen:
                continue
            if enforce_ceiling and len(events) >= self.configuration.max_events_per_run:
                return [], [], True
            seen.add(event.sha256)
            digests.append(event.sha256)
            events.append(event.model_dump())

        if unreadable:
            self.log(
                message=f"Dropped {unreadable} PolySwarm artifacts with no readable sha256",
                level="warning",
            )

        return events, digests, False

    def collect_fitting_window(
        self, window_start: datetime, window_end: datetime
    ) -> tuple[list[dict[str, Any]], list[str], datetime, bool]:
        """Collect a window, shrinking it until it fits under the per run ceiling.

        The platform answers newest first with no offset, so a window holding
        more artifacts than the ceiling cannot be drained in pieces: the only
        safe move is to ask for less time. Each attempt halves the window, which
        keeps the checkpoint moving forward instead of stalling on a busy
        period. That stall is not hypothetical, it is how this was found: a
        twelve hour window at a score of 0.9 exceeded the ceiling against the
        live service and the feed made no progress at all, with only a log line
        to say so.

        Halving stops at MIN_WINDOW_SECONDS, and there the ceiling is waived
        rather than enforced. Refusing the smallest window would be permanent:
        it cannot shrink further and the checkpoint would never move past it, so
        every later run would refuse the same window until an operator stepped
        in. Pushing it whole cannot drop anything, since the result is read to
        the end, and the price is one large batch. The ceiling exists to guard
        against a runaway request, and a one minute window is not one.

        Returns the events, their digests, the window end actually covered, and
        whether the ceiling was waived to get there.
        """
        attempt_end = window_end

        while True:
            span = (attempt_end - window_start).total_seconds()
            if span <= MIN_WINDOW_SECONDS:
                events, digests, _ = self.collect(window_start, attempt_end, enforce_ceiling=False)
                return events, digests, attempt_end, len(events) > self.configuration.max_events_per_run

            events, digests, capped = self.collect(window_start, attempt_end)
            if not capped:
                return events, digests, attempt_end, False

            attempt_end = window_start + timedelta(seconds=max(span / 2, MIN_WINDOW_SECONDS))
            self.log(
                message=(
                    f"The window held more than {self.configuration.max_events_per_run} artifacts, "
                    f"narrowing it to {int((attempt_end - window_start).total_seconds())} seconds and retrying"
                ),
                level="info",
            )

    def sleep(self, seconds: float) -> None:
        """Pause between runs, but wake up at once when Sekoia asks the connector to stop.

        Uses the SDK's own stop event rather than a bare time.sleep: a bare
        sleep would make a stop or restart request wait out the whole pause
        before the connector noticed, and Sekoia may restart an idle
        connector without warning. Separated from the caller so a test can
        drive the loop without actually waiting.
        """
        if seconds > 0:
            self._stop_event.wait(seconds)

    def backoff_seconds(self) -> float:
        """Exponential backoff after consecutive API failures, capped."""
        exponent = min(self._consecutive_failures, 10)
        return float(min(self.frequency * (2 ** max(exponent - 1, 0)), MAX_BACKOFF_SECONDS))

    def fail_cycle(self, message: str) -> int:
        """Record a failed cycle, back off, and report that nothing was pushed."""
        self._consecutive_failures += 1
        delay = self.backoff_seconds()
        self.log(
            message=f"{message}. The checkpoint is unchanged and the next attempt is in {delay:.0f} seconds",
            level="error",
        )
        self.sleep(delay)
        return 0

    def next_run(self) -> int:
        """Run one poll cycle. Returns the number of events pushed."""
        window_start = self.checkpoint.offset
        window_end = self.window_end(window_start)
        if window_end is None:
            self.sleep(self.frequency)
            return 0

        intake_key = self.configuration.intake_key
        started = time.monotonic()

        try:
            events, digests, window_end, oversized = self.collect_fitting_window(window_start, window_end)
        except Exception as exception:
            # Only the class name. The client's exception text can carry the
            # request that produced it, and the request carries the query.
            return self.fail_cycle(f"PolySwarm rejected the intel pull ({type(exception).__name__})")

        if oversized:
            self.log(
                message=(
                    f"A {MIN_WINDOW_SECONDS} second window held {len(events)} artifacts, more than "
                    f"max_events_per_run ({self.configuration.max_events_per_run}). It was pushed whole "
                    "because it cannot be made smaller. Tighten the family, tag or polyscore filter, "
                    "or raise max_events_per_run"
                ),
                level="warning",
            )

        if events:
            # The SDK never raises from a push. A chunk that still fails after
            # its retries is logged and left out of the returned ids, so the
            # shortfall is the only sign that events did not arrive.
            event_ids = self.push_events_to_intakes(events)
            if len(event_ids) < len(events):
                return self.fail_cycle(
                    f"The intake accepted {len(event_ids)} of {len(events)} events, so the window was not "
                    "marked done and will be sent again"
                )
            OUTCOMING_EVENTS.labels(intake_key=intake_key).inc(len(event_ids))
            self.log(message=f"Pushed {len(events)} PolySwarm artifacts", level="info")

        self._consecutive_failures = 0
        self.checkpoint.offset = window_end
        self.remember_digests(digests)

        now = datetime.now(UTC)
        FORWARD_EVENTS_DURATION.labels(intake_key=intake_key).observe(time.monotonic() - started)
        EVENTS_LAG.labels(intake_key=intake_key).set(max((now - window_end).total_seconds(), 0.0))

        # Wait only once the window has reached the frontier. Anything further
        # behind than one minimum window is catch up, and sleeping a full
        # frequency between slices would stretch a day of backlog over hours.
        # The tolerance also stops a connector that is already current from
        # querying again straight away for a few seconds of new time.
        frontier = now - timedelta(seconds=self.configuration.lag_seconds)
        behind = window_end < frontier - timedelta(seconds=MIN_WINDOW_SECONDS)
        self.sleep(0 if behind else self.frequency)
        return len(events)

    def run(self) -> None:  # pragma: no cover
        self.log(message="Starting the PolySwarm intel feed", level="info")
        while self.running:
            try:
                self.next_run()
            except Exception as exception:
                self.log(
                    message=f"The PolySwarm intel feed stopped unexpectedly ({type(exception).__name__})",
                    level="error",
                )
                self.sleep(self.frequency)
            # After the cycle rather than before it, including the failed ones:
            # a handled error still means the loop is turning, while a request
            # that never returns never reaches here, which is the state that
            # needs a restart.
            self.heartbeat()
        self.log(message="Stopping the PolySwarm intel feed", level="info")
