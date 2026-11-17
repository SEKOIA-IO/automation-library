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

The live endpoint returns each match as a bare sha256 string, not as an
artifact document (measured against the real API for ip, domain, ttp and
imphash pivots). The client wraps each entry unchanged, so item.json is that
string. A string item therefore yields an artifact with only sha256 and
permalink filled in. A dict item, which this action also tolerates, is read only for its sha256.
"""

import re
from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from polyswarm_api import settings as ps_settings
from pydantic import BaseModel, Field

from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.client import CLIENT_ERRORS, MISSING_RESULT, build_client, failure_kind
from polyswarm_modules.validators import invalid_domain_reason, invalid_imphash_reason, invalid_ip_reason

# A pivot on a busy indicator can match thousands of artifacts, and the client
# pages through all of them for as long as the generator is consumed. The
# endpoint has no page size argument to lean on, so both numbers are enforced
# on this side, as SearchMetadata does for the same reason.
DEFAULT_LIMIT = 20
MAX_LIMIT = 200

SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


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
    limit: int = Field(
        default=DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=(
            f"Maximum number of artifacts to return, from {1} up to a hard ceiling of "
            f"{MAX_LIMIT} so a pivot on a common indicator cannot run away. Defaults to {DEFAULT_LIMIT}."
        ),
    )


class IocArtifact(BaseModel):
    sha256: str = ""
    permalink: str = ""


class SearchIocResponse(BaseModel):
    found: bool = False
    indicator_type: str = ""
    indicator: str = ""
    results: list[IocArtifact] = Field(default_factory=list)
    returned_count: int = 0
    limit: int = DEFAULT_LIMIT
    truncated: bool = False


class SearchIoc(PolyswarmAction):
    """Pivot from an IP, domain, TTP or imphash to the PolySwarm artifacts associated with it.

    Wraps api.search_by_ioc, which the installed client accepts exactly one
    of ip, domain, ttp or imphash for. This action requires exactly one of
    the four and refuses a call that supplies none or several, since the
    client has no defined behaviour for that and guessing which one the
    caller meant would silently answer the wrong question. It only reads and
    spends no scanning quota.

    Three branches: found (PolySwarm returned at least one artifact for the
    indicator, and every one of them is in the answer), truncated (at least
    one artifact, but the limit cut the answer before the pivot was
    exhausted) and not found (PolySwarm has nothing on it). Truncated is its
    own branch so a capped answer can never be read by a playbook as a
    complete one. Not found is an ordinary outcome, not an error: most
    indicators a playbook checks were never seen by PolySwarm at all.
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

        elif indicator_type == "domain":
            reason = invalid_domain_reason(indicator, ip_action="SearchIp")
            if reason is not None:
                self.error(f"Refusing to search {reason}.")
                return None

        elif indicator_type == "imphash":
            reason = invalid_imphash_reason(indicator)
            if reason is not None:
                self.error(f"Refusing to search {reason}.")
                return None

        api = build_client(self.module.configuration)

        try:
            iterator = api.search_by_ioc(**{indicator_type: indicator})
            results, truncated = self._collect(iterator, args.limit)
        except MISSING_RESULT:
            # A 204 or 404 on the first page is the client's way of saying
            # nothing matched, and an indicator PolySwarm has never seen is an
            # ordinary outcome, not an error. A stop after items were already
            # collected is handled in _collect and never reaches here.
            results, truncated = [], False
        except ps_exceptions.InvalidValueException as exc:
            self.error(f"PolySwarm rejected '{indicator}' as an invalid {indicator_type} ({failure_kind(exc)}).")
            return None
        except CLIENT_ERRORS as exc:
            # Never quote the client's own message: it can render the whole
            # request back into the exception text, and the request carries
            # the key.
            self.error(f"PolySwarm did not run the {indicator_type} pivot ({failure_kind(exc)}).")
            return None

        if not results:
            self.set_output("not found", True)
            return SearchIocResponse(
                found=False,
                indicator_type=indicator_type,
                indicator=indicator,
                results=[],
                returned_count=0,
                limit=args.limit,
                truncated=False,
            ).model_dump()

        self.set_output("truncated" if truncated else "found", True)
        return SearchIocResponse(
            found=True,
            indicator_type=indicator_type,
            indicator=indicator,
            results=results,
            returned_count=len(results),
            limit=args.limit,
            truncated=truncated,
        ).model_dump()

    @staticmethod
    def _collect(iterator: Any, limit: int) -> tuple[list[IocArtifact], bool]:
        """Consume the pivot generator up to limit, and detect whether more remained.

        The client follows has_more across pages behind a lazily consumed
        generator, so stopping consumption is the only way to cap the quota
        and memory a broad indicator costs. The length check runs before an
        item is appended so that the item which would have exceeded the limit
        is what proves there was more, without being included in the answer.
        """
        items: list[IocArtifact] = []
        try:
            for item in iterator:
                if len(items) >= limit:
                    return items, True
                items.append(SearchIoc._build_artifact(item))
        except MISSING_RESULT:
            # The client can report "no results" part way through paging. With
            # nothing collected that is a genuine not found. With items already
            # in hand the pivot did match, so they are kept, and the answer is
            # flagged truncated because the pages after the stop were never
            # read. The response model has no separate incomplete field, and
            # truncated is the one flag a playbook already treats as "do not
            # read this as the full set".
            if items:
                return items, True
            return [], False
        return items, False

    @staticmethod
    def _build_artifact(item: Any) -> IocArtifact:
        """Reduce one pivot match to its sha256 and permalink.

        The live endpoint returns a bare sha256 string per match, and that is
        all it knows about the artifact. A dict item is still tolerated, and
        only its sha256 is read. A value that is not a sha256 is not trusted:
        the row is kept so returned_count stays honest, but sha256 and
        permalink stay blank rather than building a link from arbitrary text.
        """
        raw = getattr(item, "json", None)
        candidate: Any = raw
        if isinstance(raw, dict):
            artifact = raw.get("artifact")
            candidate = (artifact.get("sha256") if isinstance(artifact, dict) else None) or raw.get("sha256")

        if isinstance(candidate, str):
            sha256 = candidate.strip().lower()
            if SHA256_PATTERN.fullmatch(sha256):
                return IocArtifact(sha256=sha256, permalink=f"{ps_settings.DEFAULT_PERMALINK_BASE}/{sha256}")
        return IocArtifact()
