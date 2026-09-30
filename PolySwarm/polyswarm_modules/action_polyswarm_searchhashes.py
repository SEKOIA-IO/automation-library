"""Bulk hash lookup against PolySwarm.

The PolySwarm API has no batch hash endpoint. The hash search route accepts a
single hash per request (GET /search/hash/{hash_type} with one hash parameter),
so this action loops on the client side and spends one request per distinct
hash, exactly as the PolySwarm app for Splunk does. A list of fifty hashes
costs fifty requests against the configured plan, not one. The input list is
deduplicated first so a repeated hash is never paid for twice, the lookups run
sequentially, and a rate limit stops the loop immediately and returns whatever
was already gathered instead of hammering the API.
"""

import re
from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from pydantic import BaseModel, Field
from requests import RequestException

from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.client import build_client

SCAN_FAILURES: tuple[type[Exception], ...] = (
    ps_exceptions.PolyswarmException,
    RequestException,
)
MISSING_RESULT: tuple[type[Exception], ...] = (
    ps_exceptions.NoResultsException,
    ps_exceptions.NotFoundException,
)

MAX_HASHES_PER_CALL = 100

_HASH_LENGTHS: dict[int, str] = {32: "MD5", 40: "SHA1", 64: "SHA256"}
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


def _hash_kind(value: str) -> str | None:
    """Return the hash type a value plausibly is, or None when it is neither.

    A wrong-length or non-hex value is rejected before it costs an API
    request: the server would refuse it anyway, and finding that out over the
    network burns quota and a request slot for an answer that is knowable
    locally.
    """
    if not _HEX_RE.match(value):
        return None
    return _HASH_LENGTHS.get(len(value))


class SearchHashesArguments(BaseModel):
    hashes: list[str] = Field(
        ...,
        description=(
            "Hashes (SHA256, SHA1 or MD5) to look up. Read-only: nothing is submitted "
            "to PolySwarm. At most 100 distinct hashes per call, and each distinct hash "
            "costs one PolySwarm API request."
        ),
    )
    include_assertions: bool = Field(
        default=False,
        description="Include the individual engine verdicts for every hash, which makes the result much larger",
    )


class HashAssertion(BaseModel):
    engine_name: str
    author_name: str
    verdict: bool | None


class HashVerdict(BaseModel):
    hash: str
    sha256: str
    malicious_count: int
    benign_count: int
    total_count: int
    polyscore: float | None
    permalink: str
    family: str = ""
    assertions: list[HashAssertion] = []


class HashLookupError(BaseModel):
    hash: str
    reason: str


class SearchHashesResponse(BaseModel):
    results: list[HashVerdict]
    not_found: list[str]
    errors: list[HashLookupError]
    requested_count: int
    queried_count: int
    rate_limited: bool


class SearchHashes(PolyswarmAction):
    """Action to look up a list of hashes against what PolySwarm already knows.

    This is a read-only search: nothing is submitted and no scan quota is
    spent, one request per distinct hash.
    """

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        args = SearchHashesArguments(**arguments)

        wanted = self._normalize(args.hashes)
        if not wanted:
            self.error("No hashes were supplied to look up")
            return None
        if len(wanted) > MAX_HASHES_PER_CALL:
            self.error(
                f"This action looks up at most {MAX_HASHES_PER_CALL} hashes per call "
                f"and {len(wanted)} distinct hashes were supplied. "
                "Split the list across several calls."
            )
            return None

        api = build_client(self.module.configuration)

        results: list[HashVerdict] = []
        not_found: list[str] = []
        errors: list[HashLookupError] = []
        queried = 0
        rate_limited = False

        # One request per distinct hash. There is no batch route to use instead.
        for query_hash in wanted:
            if _hash_kind(query_hash) is None:
                # Rejected locally: the server would refuse this anyway, and an
                # API request is not spent finding that out.
                errors.append(
                    HashLookupError(
                        hash=query_hash,
                        reason=(
                            "Not a plausible MD5, SHA1 or SHA256 hash: expected 32, 40 or 64 hexadecimal characters"
                        ),
                    )
                )
                continue
            try:
                queried += 1
                found = list(api.search(query_hash))
            except ps_exceptions.UsageLimitsExceededException:
                # Stop on the first rate limit rather than burning the rest of
                # the list against a limit that is already refusing requests.
                rate_limited = True
                self.error(
                    f"PolySwarm rejected the lookup for usage limits on request {queried} of {len(wanted)}. "
                    f"{len(wanted) - queried} hashes were not looked up, and the results gathered "
                    "before the limit are returned. Retry the remainder later or raise the plan limit."
                )
                break
            except MISSING_RESULT:
                # The client raises on 204 and 404 rather than returning an
                # empty list, and a hash the platform has never seen is the
                # most common thing an analyst asks about. It is an answer, not
                # a failure, so it does not stop the rest of the list.
                not_found.append(query_hash)
                continue
            except ps_exceptions.InvalidValueException:
                errors.append(HashLookupError(hash=query_hash, reason="Not a valid SHA256, SHA1 or MD5 hash"))
                continue
            except SCAN_FAILURES as exc:
                # Never quote the client's own message: on some failures it
                # renders the whole request, headers included, back into the
                # exception text, which carries the key. Only the exception
                # kind is reported, in a message written here.
                errors.append(
                    HashLookupError(
                        hash=query_hash,
                        reason=f"PolySwarm did not return a result for this hash ({type(exc).__name__})",
                    )
                )
                continue

            if not found:
                not_found.append(query_hash)
                continue

            result = found[0]
            if getattr(result, "failed", False):
                errors.append(
                    HashLookupError(
                        hash=query_hash,
                        reason="PolySwarm reported the most recent scan as failed, so it carries no verdict",
                    )
                )
                continue
            if not self.is_complete(result):
                errors.append(
                    HashLookupError(
                        hash=query_hash,
                        reason=(
                            "The assertion window on the most recent scan is still open, so there is no verdict yet"
                        ),
                    )
                )
                continue

            results.append(self._build_verdict(query_hash, result, args.include_assertions))

        if not results and not not_found:
            self.error("None of the supplied hashes could be looked up in PolySwarm")
            return None

        response = SearchHashesResponse(
            results=results,
            not_found=not_found,
            errors=errors,
            requested_count=len(wanted),
            queried_count=queried,
            rate_limited=rate_limited,
        )

        # A usage limit cutting the run short means the list of hashes that
        # were never looked up is unknown territory, not a clean answer. That
        # branch takes priority over detected/not detected so a partial batch
        # can never be read as a definitive clean result.
        if response.rate_limited:
            self.set_output("partial", True)
        elif any(row.malicious_count > 0 for row in results):
            self.set_output("detected", True)
        else:
            self.set_output("not detected", True)

        return response.model_dump()

    @staticmethod
    def _normalize(hashes: list[str]) -> list[str]:
        """Trim, lowercase and deduplicate while keeping the order supplied.

        Every lookup costs a request, so the same hash written twice, or written
        once in upper case and once in lower case, is only paid for once.
        """
        seen: dict[str, None] = {}
        for value in hashes:
            candidate = value.strip().lower()
            if candidate:
                seen.setdefault(candidate, None)
        return list(seen)

    def _build_verdict(self, query_hash: str, result: Any, include_assertions: bool) -> HashVerdict:
        # Only assertions inside the bloom mask are real answers from an engine.
        # An engine that abstained answers None, and it is neither malicious nor
        # benign: counting abstentions as benign inflates the clean side of any
        # ratio a customer writes a detection rule against.
        scored = [a for a in result.assertions if a.mask]

        assertions: list[HashAssertion] = []
        if include_assertions:
            assertions = [
                HashAssertion(
                    engine_name=a.engine_name,
                    author_name=a.author_name,
                    verdict=a.verdict,
                )
                for a in scored
            ]

        return HashVerdict(
            hash=query_hash,
            sha256=result.sha256,
            malicious_count=sum(1 for a in scored if a.verdict is True),
            benign_count=sum(1 for a in scored if a.verdict is False),
            total_count=len(scored),
            polyscore=result.polyscore,
            permalink=result.permalink,
            family=self._extract_family(result),
            assertions=assertions,
        )

    @staticmethod
    def _extract_family(result: Any) -> str:
        """Read the malware family from the PolyUnite metadata when there is one."""
        metadata_json = getattr(getattr(result, "metadata", None), "json", None)
        if not isinstance(metadata_json, dict):
            return ""
        polyunite = metadata_json.get("polyunite")
        if isinstance(polyunite, dict):
            return polyunite.get("malware_family", "") or ""
        return ""
