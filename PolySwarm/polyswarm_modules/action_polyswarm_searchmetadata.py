"""Search PolySwarm's metadata index with an operator supplied query.

api.search_by_metadata takes a Lucene style query string and returns every
artifact document that matches it: the same endpoint and the same query
language polyswarm_modules/connector_polyswarm_intel_feed.py drives on a
schedule (see that file for how a query is assembled and what the index
actually accepts). This action exposes the endpoint directly instead, so a
playbook author can hand it any query rather than only the family, tag and
polyscore filters the connector builds.

This action only reads. It never submits, never waits for a scan and never
touches the sandbox, and it spends no scanning quota.

WHAT THE QUERY LANGUAGE CAN AND CANNOT DO, AND HOW THAT WAS VERIFIED

The connector's own comments state the ground truth for this client version:
every operator filter it builds (malware family, tag, polyscore, a time
window on artifact.created) is a server side Lucene term against documented
fields, sent straight to the search/metadata/query endpoint. That confirms
the endpoint accepts arbitrary Lucene terms against artifact document fields,
not just the handful the connector happens to filter on.

What this action does NOT claim, because it was not found anywhere in the
installed client (polyswarm_api 3.21.0) or its comments:

  - No documented list of every queryable field. The connector only proves
    the fields it itself queries (artifact.created, scan.latest_scan.polyscore,
    the family fields, tags). A query against a field not in that list may or
    may not match anything; this action does not promise it will.
  - No page size or offset control. api.search_by_metadata takes no limit or
    offset argument (verified by reading its signature in
    polyswarm_api/api.py); pagination is internal to the client, driven by a
    lazily consumed generator. The limit argument below is enforced entirely
    on this side, by not consuming the generator past it, exactly the
    technique the connector itself uses to bound its own runs.
  - No sort order control. The connector notes the endpoint answers newest
    first with no sort argument, and this action does not expose one because
    there is nothing to expose.

include and exclude are real, separate arguments on api.search_by_metadata
(verified by reading its signature in polyswarm_api/api.py: `def
search_by_metadata(self, query, include=None, exclude=None, ips=None,
urls=None, domains=None)`), so both are exposed here. The ips/urls/domains
narrowing arguments on that same signature are not exposed: they were not
mentioned in this action's scope and their filtering behaviour relative to
the query string was not verified.
"""

from datetime import datetime
from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from polyswarm_api import settings as ps_settings
from pydantic import BaseModel, Field

from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.client import build_client

MISSING_RESULT: tuple[type[Exception], ...] = (
    ps_exceptions.NoResultsException,
    ps_exceptions.NotFoundException,
)
NUMERIC_ERRORS: tuple[type[Exception], ...] = (TypeError, ValueError)

# A sane default that returns enough to be useful without an operator asking
# for it, and a hard ceiling a broad query cannot push past. The endpoint
# itself has no page size argument to lean on for this (see module
# docstring), so both numbers are enforced entirely on this side.
DEFAULT_LIMIT = 20
MAX_LIMIT = 200

# An empty query is a mistake, not a request for everything. A query this
# long is almost certainly a mistake too, most likely a whole file or a
# playbook variable that expanded to something unintended, and it is refused
# before it is sent rather than left for the endpoint to reject.
MAX_QUERY_LENGTH = 2000


def _as_text(value: Any) -> str:
    """Render a value as plain text, treating an absent value as empty.

    A datetime field on a metadata document does not always carry a UTC
    offset, and astimezone reads a naive datetime as the local machine's
    zone rather than as UTC, which silently shifts it. A naive value is
    therefore treated as already UTC, matching how the same problem is
    handled in connector_polyswarm_intel_feed.py.
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        from datetime import UTC

        aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return aware.astimezone(UTC).isoformat()
    return str(value)


def _as_names(value: Any) -> list[str]:
    """Normalise a families or tags payload into a deduplicated list of names."""
    if isinstance(value, str):
        candidates: list[Any] = [value]
    elif isinstance(value, (list, tuple, set)):
        candidates = list(value)
    else:
        return []

    seen: set[str] = set()
    names: list[str] = []
    for candidate in candidates:
        if isinstance(candidate, dict):
            raw = candidate.get("name") or candidate.get("tag") or candidate.get("family") or ""
        elif isinstance(candidate, str):
            raw = candidate
        else:
            continue
        name = raw.strip()
        key = name.casefold()
        if name and key not in seen:
            seen.add(key)
            names.append(name)
    return names


def _as_number(value: Any) -> int:
    """Read an integer counter, treating anything unreadable as zero."""
    try:
        return int(value)
    except NUMERIC_ERRORS:
        return 0


def _as_score(value: Any) -> float | None:
    """Read a polyscore, treating anything unreadable as absent."""
    try:
        return float(value)
    except NUMERIC_ERRORS:
        return None


def _first_present(*values: Any) -> Any:
    """Return the first value that is not None, or None when every value is.

    A parsed attribute that genuinely reads as zero (zero detections is a
    real, meaningful count) must not be treated as absent and fall through to
    the next source: `0 or fallback` would do exactly that, silently
    replacing a true zero with whatever the fallback happens to hold.
    """
    for value in values:
        if value is not None:
            return value
    return None


class SearchMetadataArguments(BaseModel):
    query: str = Field(
        ...,
        description=(
            "Lucene style query against the PolySwarm metadata search endpoint, for example "
            "'scan.latest_scan.polyscore:>=0.9 AND tags:\"ransomware\"'. This action only reads "
            "the index and spends no scanning quota."
        ),
    )
    limit: int = Field(
        default=DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=(
            f"Maximum number of matching artifacts to return, from {1} up to a hard ceiling of "
            f"{MAX_LIMIT} so a broad query cannot run away. Defaults to {DEFAULT_LIMIT}."
        ),
    )
    include: list[str] = Field(
        default_factory=list,
        description=(
            "Fields to include in each returned document, wildcard suffixes accepted (for example "
            "'scan.*'). Passed straight through to the PolySwarm metadata endpoint. Leave empty to "
            "let the endpoint decide what a document carries."
        ),
    )
    exclude: list[str] = Field(
        default_factory=list,
        description=(
            "Fields to exclude from each returned document, wildcard suffixes accepted. Passed "
            "straight through to the PolySwarm metadata endpoint."
        ),
    )


class MetadataArtifact(BaseModel):
    sha256: str = ""
    sha1: str = ""
    md5: str = ""
    malicious_detections: int = 0
    benign_detections: int = 0
    total_detections: int = 0
    polyscore: float | None = None
    permalink: str = ""
    family: str = ""
    families: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    first_seen: str = ""
    last_scanned: str = ""
    mimetype: str = ""
    filenames: list[str] = Field(default_factory=list)


class SearchMetadataResponse(BaseModel):
    found: bool = False
    results: list[MetadataArtifact] = Field(default_factory=list)
    returned_count: int = 0
    limit: int = DEFAULT_LIMIT
    truncated: bool = False


class SearchMetadata(PolyswarmAction):
    """Run an operator supplied Lucene style query against the PolySwarm metadata index.

    This is the most direct way a playbook can reach api.search_by_metadata,
    the single most powerful read surface the PolySwarm API exposes: an
    arbitrary query against every artifact document PolySwarm holds, rather
    than the fixed set of filters an individual action or the intel feed
    connector applies. The action only reads and spends no scanning quota.

    Three branches: found (at least one match, and every match requested was
    returned), truncated (at least one match, but the limit cut the answer
    before the query was exhausted), and not found (no matches at all). The
    truncated branch exists on its own, separate from found, so a capped
    answer can never be read by a playbook as a complete one.
    """

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        args = SearchMetadataArguments(**arguments)

        query = args.query.strip()
        if not query:
            self.error("Refusing an empty query: supply a Lucene style metadata query to search for")
            return None
        if len(query) > MAX_QUERY_LENGTH:
            self.error(
                f"Refusing a query longer than {MAX_QUERY_LENGTH} characters "
                f"({len(query)} characters supplied): narrow the query before retrying"
            )
            return None

        api = build_client(self.module.configuration)

        try:
            iterator = api.search_by_metadata(
                query,
                include=args.include or None,
                exclude=args.exclude or None,
            )
            results, truncated = self._collect(iterator, args.limit)
        except MISSING_RESULT:
            # A 204 or 404 is the client's way of saying nothing matched, on
            # the first page or any later one, and is not an error.
            results, truncated = [], False
        except ps_exceptions.InvalidValueException as exc:
            self.error(
                f"PolySwarm rejected the query as malformed ({type(exc).__name__}). "
                "Check the field names and the Lucene syntax."
            )
            return None
        except ps_exceptions.PolyswarmException as exc:
            # Never quote the client's own message: it can render the whole
            # request back into the exception text, and the request carries
            # the key.
            self.error(f"PolySwarm did not run the metadata search ({type(exc).__name__}).")
            return None

        if not results:
            self.set_output("not found", True)
            return SearchMetadataResponse(
                found=False,
                results=[],
                returned_count=0,
                limit=args.limit,
                truncated=False,
            ).model_dump()

        response = SearchMetadataResponse(
            found=True,
            results=results,
            returned_count=len(results),
            limit=args.limit,
            truncated=truncated,
        )

        if truncated:
            self.set_output("truncated", True)
        else:
            self.set_output("found", True)

        return response.model_dump()

    @staticmethod
    def _collect(iterator: Any, limit: int) -> tuple[list[MetadataArtifact], bool]:
        """Consume the search generator up to limit, and detect whether more remained.

        The client owns pagination internally behind a lazily consumed
        generator, with no offset or limit argument of its own (see the
        module docstring). Stopping consumption is therefore the only way to
        cap the work, and the length check runs before an item is appended
        so that the item which would have exceeded the limit is what proves
        there was more to find, without being included in the answer.
        """
        items: list[MetadataArtifact] = []
        truncated = False
        for item in iterator:
            if len(items) >= limit:
                truncated = True
                break
            items.append(SearchMetadata._build_artifact(item))
        return items, truncated

    @staticmethod
    def _build_artifact(item: Any) -> MetadataArtifact:
        document: dict[str, Any] = getattr(item, "json", None) or {}
        scan: dict[str, Any] = document.get("scan") or {}
        latest_scan: dict[str, Any] = scan.get("latest_scan") or {}
        detections: dict[str, Any] = scan.get("detections") or {}
        polyunite: dict[str, Any] = document.get("polyunite") or {}

        family = polyunite.get("malware_family", "") if isinstance(polyunite, dict) else ""
        families = _as_names(family) + _as_names(document.get("families"))

        sha256 = _as_text(getattr(item, "sha256", "") or document.get("artifact", {}).get("sha256", "")).lower()
        permalink = f"{ps_settings.DEFAULT_PERMALINK_BASE}/{sha256}" if sha256 else ""

        return MetadataArtifact(
            sha256=sha256,
            sha1=_as_text(getattr(item, "sha1", "")),
            md5=_as_text(getattr(item, "md5", "")),
            malicious_detections=_as_number(
                _first_present(getattr(item, "malicious", None), detections.get("malicious"))
            ),
            benign_detections=_as_number(_first_present(getattr(item, "benign", None), detections.get("benign"))),
            total_detections=_as_number(
                _first_present(getattr(item, "total_detections", None), detections.get("total"))
            ),
            polyscore=_as_score(latest_scan.get("polyscore")),
            permalink=permalink,
            family=family or "",
            families=_as_names(families),
            tags=_as_names(document.get("tags")),
            first_seen=_as_text(getattr(item, "first_seen", "")),
            last_scanned=_as_text(getattr(item, "last_scanned", "")),
            mimetype=_as_text(getattr(item, "mimetype", "")),
            filenames=_as_names(getattr(item, "filenames", None)),
        )
