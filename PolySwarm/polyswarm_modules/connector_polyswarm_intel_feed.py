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

The SDK also drops, without an id and without raising, any single event longer
than EVENT_BYTES_MAX_SIZE (250000 characters of JSON). Left alone that reads as
a failed push, and since the next attempt rebuilds the same window with the same
event, it would fail forever. Two things prevent it. The list fields of an event
are capped (see MAX_LIST_ITEMS), which is what makes an oversized event possible
in the first place, and any event still over the limit is dropped and counted
here, before the push, so the id comparison only covers events that were really
submitted. The limit is measured the way the SDK measures it.

CATCH UP PACING

A run that reaches the frontier (now minus lag_seconds) sleeps for the
configured frequency. A run that stops short of it, because the window was
capped at MAX_WINDOW_MINUTES or halved, does not sleep, so a connector that was
down for a day or a month walks forward as fast as the API answers instead of
one slice per frequency.

On a busy backlog the span that fits under max_events_per_run is found by
halving, and every discarded attempt reads up to max_events_per_run + 1 results.
The span that last fit is therefore remembered between runs, next to the
digests, and the next run starts from it rather than from MAX_WINDOW_MINUTES. A
run that fits doubles it again, up to MAX_WINDOW_MINUTES, so a backlog that has
cleared is walked at full width again.

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
exception class name and message, and the message first goes through the
trigger's redaction, which strips the key. The client's own exception text can
embed the request parameters that produced it, so an exception is never
formatted into a log line raw.

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
would otherwise do to it. See format_window_bound and coerce.as_text.
"""

import json
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
from sekoia_automation.constants import EVENT_BYTES_MAX_SIZE
from sekoia_automation.storage import PersistentJSON

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.client import MISSING_RESULT, build_client, redact_key
from polyswarm_modules.coerce import NUMERIC_ERRORS, as_names, as_score, as_text
from polyswarm_modules.metrics import COLLECTED_EVENTS, EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS

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

# The SDK retries every chunk for up to 3600 seconds (stop_after_delay(3600)),
# and the attempt that straddles that deadline can still run for its 30 second
# request timeout plus a retry wait of up to 10 seconds. Chunks go out in
# parallel, so that is also the longest one push can take.
PUSH_RETRY_CEILING_SECONDS = 3600 + 30 + 10

DIGEST_FILE_NAME = "polyswarm_intel_feed.json"
WINDOW_KEY = "window_seconds"

# Caps on the list fields of one event. The three lists are unbounded in the
# metadata document, and one artifact submitted under thousands of names is
# enough to push an event past the SDK's per event limit. With these caps the
# three lists together stay near 155000 characters, under the 250000 limit.
MAX_LIST_ITEMS = 100
MAX_ITEM_CHARACTERS = 512

# Failures that mean one document could not be turned into an event. A document
# is data from outside, so a field of an unexpected type (a string where an
# object was expected, a number too large to convert) is an unreadable artifact,
# not a reason to stop the feed. pydantic's ValidationError is a ValueError.
EVENT_BUILD_ERRORS: tuple[type[Exception], ...] = (
    AttributeError,
    KeyError,
    OverflowError,
    TypeError,
    ValueError,
)

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


def _capped(names: list[str]) -> list[str]:
    """Bound a list of names in both length and item size, keeping the first ones."""
    return [name[:MAX_ITEM_CHARACTERS] for name in names[:MAX_LIST_ITEMS]]


def event_characters(event: dict[str, Any]) -> int:
    """Length of an event the way the SDK measures it against EVENT_BYTES_MAX_SIZE."""
    return len(json.dumps(event, ensure_ascii=False, separators=(",", ":")))


def _as_number(value: Any) -> int | None:
    """Read an integer counter, treating anything unreadable as absent."""
    try:
        return int(value)
    except NUMERIC_ERRORS:
        return None


class TruncatedWindowError(Exception):
    """A later page answered with no result after earlier pages had delivered some.

    The window was read only in part, so it must not be marked done.
    """


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
        # True once the "matched nothing" line has been said for the current
        # run of idle cycles. Reset when anything else happens.
        self._idle_announced = False
        # Artifacts dropped while reading the window, by reason. Reset by each
        # collect, so after collect_fitting_window it describes the final attempt.
        self._dropped: dict[str, int] = {}

    def redact(self, error: Exception) -> str:
        """Message of an error with the API key removed."""
        return redact_key(error, self.module.configuration.apikey)

    @property
    def frequency(self) -> int:
        return self.configuration.frequency

    @property
    def last_heartbeat_threshold(self) -> int:  # type: ignore[override]
        """How long without a completed cycle before the platform restarts this.

        Generous on purpose. A cycle ends with a sleep of up to the configured
        frequency, and the longest a cycle can go without finishing is a push
        that the SDK keeps retrying for its full hour (PUSH_RETRY_CEILING_SECONDS)
        followed by the back off that a failed push earns. Anything tighter
        would restart a connector that is merely waiting out an intake outage.
        Read before the configuration is attached, it answers zero, which the
        SDK reads as no check.
        """
        if not getattr(self, "configuration", None):
            return 0
        return max(3 * self.frequency, PUSH_RETRY_CEILING_SECONDS + max(MAX_BACKOFF_SECONDS, self.frequency))

    @property
    def checkpoint(self) -> CheckpointDatetime:
        """The SDK checkpoint holding the end of the last window covered whole."""
        if self._checkpoint is None:
            self.warn_if_checkpoint_clamped()
            self._checkpoint = CheckpointDatetime(
                path=self.data_path,
                start_at=timedelta(minutes=self.configuration.lookback_minutes),
                ignore_older_than=timedelta(minutes=MAX_LOOKBACK_MINUTES),
            )
        return self._checkpoint

    def warn_if_checkpoint_clamped(self) -> None:
        """Say so when a stored checkpoint is older than the lookback ceiling.

        The SDK moves such a checkpoint forward to the ceiling without a word,
        which skips whatever lay in between. The operator should be told that
        a stretch of time was not pulled.
        """
        with PersistentJSON("context.json", self.data_path) as cache:
            stored = cache.get("most_recent_date_seen")
        if not stored:
            return
        try:
            moment = datetime.fromisoformat(str(stored))
        except EVENT_BUILD_ERRORS:
            return
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        limit = datetime.now(UTC) - timedelta(minutes=MAX_LOOKBACK_MINUTES)
        if moment < limit:
            self.log(
                message=(
                    f"The saved checkpoint ({format_window_bound(moment)} UTC) is older than the "
                    f"{MAX_LOOKBACK_MINUTES} minute lookback ceiling, so the connector resumes from "
                    f"{format_window_bound(limit)} UTC. Artifacts created in between are not pulled"
                ),
                level="warning",
            )

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
        candidate = min(frontier, window_start + timedelta(seconds=self.window_span_seconds()))
        if candidate <= window_start:
            return None
        return candidate

    def window_span_seconds(self) -> int:
        """The span a run starts from: the last one that fit, else the ceiling."""
        ceiling = MAX_WINDOW_MINUTES * 60
        with self.digests as cache:
            stored = cache.get(WINDOW_KEY)
        if isinstance(stored, bool) or not isinstance(stored, int | float):
            return ceiling
        return int(min(max(stored, MIN_WINDOW_SECONDS), ceiling))

    def remember_window_span(self, covered: timedelta, halved: bool) -> None:
        """Keep the span for the next run: what fit after halving, doubled after a clean fit."""
        ceiling = MAX_WINDOW_MINUTES * 60
        seconds = covered.total_seconds()
        if halved:
            span = max(seconds, MIN_WINDOW_SECONDS)
        else:
            span = max(self.window_span_seconds(), min(seconds * 2, ceiling))
        span = int(min(span, ceiling))
        if span == self.window_span_seconds():
            return
        with self.digests as cache:
            cache[WINDOW_KEY] = span

    def build_event(self, item: Any) -> IntelFeedEvent | None:
        """Turn one metadata document into an event, or None when it is unreadable.

        An artifact with no readable sha256 has nothing an analyst can pivot on
        and nothing the connector can deduplicate on, so it is dropped rather
        than emitted half formed. A document whose fields cannot be converted
        raises one of EVENT_BUILD_ERRORS, which the caller counts the same way.
        """
        document: dict[str, Any] = getattr(item, "json", None) or {}
        artifact: dict[str, Any] = document.get("artifact") or {}
        latest_scan: dict[str, Any] = (document.get("scan") or {}).get("latest_scan") or {}
        polyunite: dict[str, Any] = document.get("polyunite") or {}

        sha256 = as_text(getattr(item, "sha256", "") or artifact.get("sha256", "")).strip()
        if not sha256:
            return None

        polyscore = as_score(getattr(item, "polyscore", None) or latest_scan.get("polyscore"))

        families = _capped(as_names(as_names(polyunite.get("malware_family")) + as_names(document.get("families"))))
        created = as_text(getattr(item, "created", None))

        return IntelFeedEvent(
            timestamp=created,
            sha256=sha256.lower(),
            sha1=as_text(getattr(item, "sha1", "")),
            md5=as_text(getattr(item, "md5", "")),
            polyscore=polyscore,
            polyscore_band=polyscore_band(polyscore),
            malicious_detections=_as_number(getattr(item, "malicious", None)),
            benign_detections=_as_number(getattr(item, "benign", None)),
            total_detections=_as_number(getattr(item, "total_detections", None)),
            families=families,
            tags=_capped(as_names(document.get("tags"))),
            first_seen=as_text(getattr(item, "first_seen", "")),
            last_scanned=as_text(getattr(item, "last_scanned", "")),
            mimetype=as_text(getattr(item, "mimetype", "")),
            extended_mimetype=as_text(getattr(item, "extended_mimetype", "")),
            filenames=_capped(as_names(getattr(item, "filenames", None))),
            permalink=f"{ps_settings.DEFAULT_PERMALINK_BASE}/{sha256.lower()}",
            community=as_text(document.get("community") or document.get("meta_community") or ""),
        )

    def remembered_digests(self) -> set[str]:
        """Digests the previous run emitted, which the boundary would repeat."""
        with self.digests as cache:
            stored = cache.get("emitted_digests") or []
        return {str(digest) for digest in stored}

    def remember_digests(self, digests: list[str]) -> None:
        """Record this run's digests so the next run can refuse the boundary repeat.

        Digests already remembered are kept behind the new ones, up to the cap.
        A retry of a window whose digests were saved before a crash dedupes every
        event and so has no digests of its own, and replacing the list with that
        empty one would forget the boundary it exists to remember.
        """
        with self.digests as cache:
            previous = [str(digest) for digest in cache.get("emitted_digests") or []]
            fresh = set(digests)
            merged = digests + [digest for digest in previous if digest not in fresh]
            cache["emitted_digests"] = merged[:MAX_REMEMBERED_DIGESTS]

    def results(self, api: PolyswarmAPI, query: str) -> Iterator[Any]:
        """Walk every page of a metadata search.

        The client returns a generator that fetches the next page on demand, so
        pagination happens by consuming this. Every later page is a full request
        run through the same response parsing as the first, so a 204 or a 404 can
        come back on any page, not only the first.

        On the first page it means the window is empty, which is a clean result.
        After at least one artifact has been yielded it cannot be told apart from
        a truncated window, and treating it as the end would advance the
        checkpoint past artifacts that were never read. It raises
        TruncatedWindowError instead, so the cycle fails and the window is asked
        for again.
        """
        yielded = 0
        try:
            for item in api.search_by_metadata(query):
                yielded += 1
                yield item
        except MISSING_RESULT as missing:
            if yielded:
                raise TruncatedWindowError(
                    f"a later page answered with no result after {yielded} artifacts ({type(missing).__name__})"
                ) from missing

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
        duplicates = 0
        self._dropped = {}

        for item in self.results(api, query):
            # The dump sits inside the guard with the build, so one document that
            # cannot be turned into an event is counted and skipped, never
            # allowed to abandon the rest of the window.
            try:
                event = self.build_event(item)
                dumped = event.model_dump() if event is not None else None
            except EVENT_BUILD_ERRORS:
                event = None
                dumped = None
            if event is None or dumped is None:
                unreadable += 1
                continue
            if event.sha256 in seen or event.sha256 in already_seen:
                duplicates += 1
                continue
            if enforce_ceiling and len(events) >= self.configuration.max_events_per_run:
                return [], [], True
            seen.add(event.sha256)
            digests.append(event.sha256)
            events.append(dumped)

        self._dropped = {"duplicate": duplicates, "unreadable": unreadable}

        if unreadable:
            self.log(
                message=(
                    f"Dropped {unreadable} PolySwarm artifacts that could not be read "
                    "(no sha256, or a field that could not be converted)"
                ),
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
        self._idle_announced = False
        delay = self.backoff_seconds()
        self.log(
            message=f"{message}. The checkpoint is unchanged and the next attempt is in {delay:.0f} seconds",
            level="error",
        )
        self.sleep(delay)
        return 0

    def next_run(self) -> int:  # type: ignore[override]
        """Run one poll cycle. Returns the number of events pushed.

        The SDK declares no return value. The count is returned so the tests
        can assert what a cycle did without reading the intake.
        """
        window_start = self.checkpoint.offset
        window_end = self.window_end(window_start)
        if window_end is None:
            self.sleep(self.frequency)
            return 0

        intake_key = self.configuration.intake_key
        started = time.monotonic()
        requested_end = window_end

        try:
            events, digests, window_end, oversized = self.collect_fitting_window(window_start, window_end)
        except TruncatedWindowError as exception:
            # Part of the window was read and then the feed answered empty. The
            # checkpoint stays put so the whole window is asked for again.
            return self.fail_cycle(f"The PolySwarm intel pull was cut short, {exception}")
        except Exception as exception:
            # The client's exception text can carry the request that produced
            # it, and the request carries the query, so the message goes through
            # the key redaction the trigger uses.
            return self.fail_cycle(
                f"PolySwarm rejected the intel pull ({type(exception).__name__}: {self.redact(exception)})"
            )

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

        events, digests, dropped = self.drop_oversized(events, digests)
        self._dropped["oversized"] = dropped
        if dropped:
            self.log(
                message=(
                    f"Dropped {dropped} PolySwarm artifacts whose event was longer than "
                    f"{EVENT_BYTES_MAX_SIZE} characters, the most the intake accepts for one event"
                ),
                level="warning",
            )

        if events:
            # The SDK never raises from a push. A chunk that still fails after
            # its retries is logged and left out of the returned ids, so the
            # shortfall is the only sign that events did not arrive.
            # The SDK accepts dicts, strings or models, and a list is invariant,
            # so the wider element type has to be spelled out to hand ours over.
            payload: list[dict[str, Any] | str | BaseModel] = list(events)
            event_ids = self.push_events_to_intakes(payload)
            if len(event_ids) < len(events):
                return self.fail_cycle(
                    f"The intake accepted {len(event_ids)} of {len(events)} events, so the window was not "
                    "marked done and will be sent again"
                )
            OUTCOMING_EVENTS.labels(intake_key=intake_key).inc(len(event_ids))
            self.log(message=f"Pushed {len(events)} PolySwarm artifacts", level="info")

        for reason, count in self._dropped.items():
            if count:
                COLLECTED_EVENTS.labels(intake_key=intake_key, reason=reason).inc(count)

        self._consecutive_failures = 0
        # Digests first. A crash between the two writes then leaves the window
        # open with its digests saved, so the retry refuses every event it
        # already pushed. The other order leaves the window closed with no
        # digests, and the next window's boundary artifact is pushed twice.
        self.remember_digests(digests)
        self.checkpoint.offset = window_end
        self.remember_window_span(window_end - window_start, halved=window_end < requested_end)

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

        if events or dropped:
            self._idle_announced = False
        elif not behind and not self._idle_announced:
            self._idle_announced = True
            # A feed filtered to one malware family can legitimately match
            # nothing for days, and a connector that says nothing at all while
            # doing that is indistinguishable from one that is broken. Said only
            # once the connector has reached the frontier, so catching up over a
            # long backlog does not write a line per slice.
            self.log(
                message=(
                    f"No PolySwarm artifacts matched {self.filter_summary()} in the window ending "
                    f"{format_window_bound(window_end)}. The connector is up to date and will look again "
                    f"every {self.frequency} seconds. This is said once, and again after the feed "
                    "has delivered events or failed."
                ),
                level="info",
            )

        self.sleep(0 if behind else self.frequency)
        return len(events)

    def drop_oversized(
        self, events: list[dict[str, Any]], digests: list[str]
    ) -> tuple[list[dict[str, Any]], list[str], int]:
        """Remove events the SDK would silently discard, so the push only covers what it can send.

        Events and digests are parallel lists, so a dropped event takes its
        digest with it. Returns what is left and how many were dropped.
        """
        kept_events: list[dict[str, Any]] = []
        kept_digests: list[str] = []
        for event, digest in zip(events, digests, strict=True):
            if event_characters(event) > EVENT_BYTES_MAX_SIZE:
                continue
            kept_events.append(event)
            kept_digests.append(digest)
        return kept_events, kept_digests, len(events) - len(kept_events)

    def filter_summary(self) -> str:
        """The operator's filters in one phrase, for a log line they can act on.

        An empty feed is nearly always the filters rather than a fault, so the
        message that reports it has to show what was asked for.
        """
        parts = [f"a PolyScore of at least {self.configuration.min_polyscore}"]
        if self.configuration.families:
            parts.append("families " + ", ".join(self.configuration.families))
        if self.configuration.tags:
            parts.append("tags " + ", ".join(self.configuration.tags))
        return " and ".join(parts)

    def run(self) -> None:  # pragma: no cover
        self.log(message="Starting the PolySwarm intel feed", level="info")
        while self.running:
            try:
                self.next_run()
            except Exception as exception:
                self.log(
                    message=(
                        "The PolySwarm intel feed stopped unexpectedly "
                        f"({type(exception).__name__}: {self.redact(exception)})"
                    ),
                    level="error",
                )
                self.sleep(self.frequency)
            # After the cycle rather than before it, including the failed ones:
            # a handled error still means the loop is turning, while a request
            # that never returns never reaches here, which is the state that
            # needs a restart.
            self.heartbeat()
        self.log(message="Stopping the PolySwarm intel feed", level="info")
