"""Pivot from an indicator of compromise to the PolySwarm artifacts that touched it.

api.search_by_ioc takes exactly one of an IP address, a domain, a TTP
identifier or an imphash and returns the artifacts PolySwarm has associated
with it (verified by reading its signature in polyswarm_api/api.py: `def
search_by_ioc(self, ip=None, domain=None, ttp=None, imphash=None)`, which
matches the four arguments this action exposes one for one). This is the
pivot capability the PolySwarm app for Splunk has and this integration
otherwise lacks: an analyst holding a C2 address, and nothing else, can ask
what samples talked to it.

This action only reads. It never submits, never waits for a scan and never
touches the sandbox, and it spends no scanning quota.

The response items the installed client hands back from this call carry no
parsed attributes of their own (unlike a hash search result): the client
wraps the raw response JSON without extracting specific fields. This action
reads that JSON through the same artifact document paths already
established elsewhere in this module (artifact.sha256, scan.detections.*,
scan.latest_scan.polyscore, polyunite.malware_family, tags), because that is
the one document shape this codebase has verified PolySwarm uses for an
artifact. A field absent from a particular response is left blank rather
than guessed at.
"""

from datetime import datetime
from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from polyswarm_api import settings as ps_settings
from pydantic import BaseModel, Field

from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.client import build_client
from polyswarm_modules.validators import invalid_ip_reason

MISSING_RESULT: tuple[type[Exception], ...] = (
    ps_exceptions.NoResultsException,
    ps_exceptions.NotFoundException,
)
NUMERIC_ERRORS: tuple[type[Exception], ...] = (TypeError, ValueError)


def _as_text(value: Any) -> str:
    """Render a value as plain text, treating an absent value as empty.

    A datetime field on an artifact document does not always carry a UTC
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


class SearchIocArguments(BaseModel):
    ip: str | None = Field(
        default=None,
        description=(
            "Pivot on this IP address: return the artifacts PolySwarm has seen communicate with it. "
            "This action only reads and spends no scanning quota. Supply exactly one of ip, domain, "
            "ttp or imphash."
        ),
    )
    domain: str | None = Field(
        default=None,
        description=(
            "Pivot on this domain: return the artifacts PolySwarm has seen communicate with it. "
            "This action only reads and spends no scanning quota. Supply exactly one of ip, domain, "
            "ttp or imphash."
        ),
    )
    ttp: str | None = Field(
        default=None,
        description=(
            "Pivot on this TTP identifier, as PolySwarm's sandbox analysis records it: return the "
            "artifacts associated with it. This action only reads and spends no scanning quota. "
            "Supply exactly one of ip, domain, ttp or imphash."
        ),
    )
    imphash: str | None = Field(
        default=None,
        description=(
            "Pivot on this import hash (imphash): return the artifacts PolySwarm has seen share it. "
            "This action only reads and spends no scanning quota. Supply exactly one of ip, domain, "
            "ttp or imphash."
        ),
    )


class IocArtifact(BaseModel):
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


class SearchIocResponse(BaseModel):
    found: bool = False
    indicator_type: str = ""
    indicator: str = ""
    results: list[IocArtifact] = Field(default_factory=list)
    returned_count: int = 0


class SearchIoc(PolyswarmAction):
    """Pivot from an IP, domain, TTP or imphash to the PolySwarm artifacts associated with it.

    Wraps api.search_by_ioc, which the installed client accepts exactly one
    of ip, domain, ttp or imphash for. This action requires exactly one of
    the four and refuses a call that supplies none or several, since the
    client has no defined behaviour for that and guessing which one the
    caller meant would silently answer the wrong question. It only reads and
    spends no scanning quota.

    Two branches: found (PolySwarm returned at least one artifact for the
    indicator) and not found (PolySwarm has nothing on it). Not found is an
    ordinary outcome, not an error: most indicators a playbook checks were
    never seen by PolySwarm at all.
    """

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        args = SearchIocArguments(**arguments)

        # A field a playbook left empty arrives as an empty string rather
        # than as nothing at all, and whitespace does not count as supplied.
        provided = {
            name: value.strip()
            for name, value in (
                ("ip", args.ip),
                ("domain", args.domain),
                ("ttp", args.ttp),
                ("imphash", args.imphash),
            )
            if value and value.strip()
        }

        if not provided:
            self.error("Supply exactly one of ip, domain, ttp or imphash to pivot on: none were supplied")
            return None
        if len(provided) > 1:
            self.error(
                "Supply exactly one of ip, domain, ttp or imphash to pivot on: "
                f"{', '.join(sorted(provided))} were supplied together"
            )
            return None

        indicator_type, indicator = next(iter(provided.items()))

        if indicator_type == "ip":
            reason = invalid_ip_reason(indicator)
            if reason is not None:
                self.error(f"Refusing to search {reason}.")
                return None

        api = build_client(self.module.configuration)

        try:
            iterator = api.search_by_ioc(**{indicator_type: indicator})
            results = [self._build_artifact(item) for item in iterator]
        except MISSING_RESULT:
            # A 204 or 404 is the client's way of saying nothing matched, and
            # an indicator PolySwarm has never seen is an ordinary outcome,
            # not an error.
            results = []
        except ps_exceptions.InvalidValueException as exc:
            self.error(f"PolySwarm rejected '{indicator}' as an invalid {indicator_type} ({type(exc).__name__}).")
            return None
        except ps_exceptions.PolyswarmException as exc:
            # Never quote the client's own message: it can render the whole
            # request back into the exception text, and the request carries
            # the key.
            self.error(f"PolySwarm did not run the {indicator_type} pivot ({type(exc).__name__}).")
            return None

        if not results:
            self.set_output("not found", True)
            return SearchIocResponse(
                found=False,
                indicator_type=indicator_type,
                indicator=indicator,
                results=[],
                returned_count=0,
            ).model_dump()

        self.set_output("found", True)
        return SearchIocResponse(
            found=True,
            indicator_type=indicator_type,
            indicator=indicator,
            results=results,
            returned_count=len(results),
        ).model_dump()

    @staticmethod
    def _build_artifact(item: Any) -> IocArtifact:
        document: dict[str, Any] = getattr(item, "json", None) or {}
        artifact: dict[str, Any] = document.get("artifact") or {}
        scan: dict[str, Any] = document.get("scan") or {}
        latest_scan: dict[str, Any] = scan.get("latest_scan") or {}
        detections: dict[str, Any] = scan.get("detections") or {}
        polyunite: dict[str, Any] = document.get("polyunite") or {}

        family = polyunite.get("malware_family", "") if isinstance(polyunite, dict) else ""
        families = _as_names(family) + _as_names(document.get("families"))

        sha256 = _as_text(artifact.get("sha256") or document.get("sha256")).lower()
        permalink = f"{ps_settings.DEFAULT_PERMALINK_BASE}/{sha256}" if sha256 else ""

        return IocArtifact(
            sha256=sha256,
            sha1=_as_text(artifact.get("sha1") or document.get("sha1")),
            md5=_as_text(artifact.get("md5") or document.get("md5")),
            malicious_detections=_as_number(detections.get("malicious")),
            benign_detections=_as_number(detections.get("benign")),
            total_detections=_as_number(detections.get("total")),
            polyscore=_as_score(latest_scan.get("polyscore")),
            permalink=permalink,
            family=family or "",
            families=_as_names(families),
            tags=_as_names(document.get("tags")),
            first_seen=_as_text(scan.get("first_scan", {}).get("created") if isinstance(scan, dict) else None),
            last_scanned=_as_text(latest_scan.get("created")),
            mimetype=_as_text((scan.get("mimetype") or {}).get("mime")),
            filenames=_as_names(scan.get("filename")),
        )
