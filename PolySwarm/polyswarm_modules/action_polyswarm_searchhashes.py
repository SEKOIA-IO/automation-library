"""Bulk hash lookup against PolySwarm.

The PolySwarm API has no batch hash endpoint. The hash search route accepts a
single hash per request (GET /search/hash/{hash_type} with one hash parameter),
so this action loops on the client side and spends one request per distinct
hash, exactly as the PolySwarm app for Splunk does. A list of fifty hashes
costs fifty requests against the configured plan, not one. The input list is
deduplicated first so a repeated hash is never paid for twice, the lookups run
sequentially, and the loop stops and returns whatever was already gathered, as
a partial run, on a rate limit, a refused key (401 or 403), a transport error,
three failures in a row, or when the overall time bound is spent, instead of
hammering an API that is not answering. Any hash that could not be
checked sends the run to the partial branch, never to not detected.
"""

import time
from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from pydantic import BaseModel, Field
from requests import RequestException

from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.client import CLIENT_ERRORS, MISSING_RESULT, build_client, failure_kind, status_of
from polyswarm_modules.scan import MAX_WAIT_SECONDS_CEILING
from polyswarm_modules.validators import hash_kind
from polyswarm_modules.verdict import AssertionResult, tally_assertions

MAX_HASHES_PER_CALL = 100
# A bad key, an outage or a slow platform must not let a hundred lookups run for
# hours. The longest any action here tells a playbook it may wait is the scan
# wait ceiling, so the whole loop is held to the same bound.
DEADLINE_SECONDS: int = MAX_WAIT_SECONDS_CEILING
# Consecutive lookups that fail for any reason other than "no such hash". A
# healthy answer in between resets the count, so a single bad hash never stops a run.
MAX_CONSECUTIVE_FAILURES: int = 3
# The key is refused, so every further request would be refused as well.
AUTH_STATUSES: frozenset[int] = frozenset({401, 403})
# Failures that say the platform or the network is unreachable, not that one hash is bad.
TRANSPORT_ERRORS: tuple[type[Exception], ...] = (RequestException, ps_exceptions.TimeoutException)


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


class HashVerdict(BaseModel):
    hash: str
    sha256: str
    malicious_count: int
    benign_count: int
    total_count: int
    polyscore: float | None
    permalink: str
    family: str = ""
    assertions: list[AssertionResult] = []


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
        stopped_early = False
        consecutive_failures = 0
        deadline = time.monotonic() + DEADLINE_SECONDS

        # One request per distinct hash. There is no batch route to use instead.
        for query_hash in wanted:
            if time.monotonic() >= deadline:
                stopped_early = True
                self.log(
                    f"The {DEADLINE_SECONDS} second time bound for this action was reached after {queried} of "
                    f"{len(wanted)} lookups. The results gathered so far are returned.",
                    level="warning",
                )
                break
            if hash_kind(query_hash) is None:
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
                # Only the most recent result is read, so do not follow every page.
                found = next(iter(api.search(query_hash)), None)
            except ps_exceptions.UsageLimitsExceededException:
                # Stop on the first rate limit rather than burning the rest of
                # the list against a limit that is already refusing requests.
                rate_limited = True
                # Not self.error(): that marks the whole run as failed, and the
                # partial branch below exists to deliver what was gathered.
                self.log(
                    f"PolySwarm rejected the lookup for usage limits on request {queried} of {len(wanted)}. "
                    f"{len(wanted) - queried} hashes were not looked up, and the results gathered "
                    "before the limit are returned. Retry the remainder later or raise the plan limit.",
                    level="warning",
                )
                break
            except MISSING_RESULT:
                # The client raises on 204 and 404 rather than returning an
                # empty list, and a hash the platform has never seen is the
                # most common thing an analyst asks about. It is an answer, not
                # a failure, so it does not stop the rest of the list.
                not_found.append(query_hash)
                consecutive_failures = 0
                continue
            except ps_exceptions.InvalidValueException:
                errors.append(HashLookupError(hash=query_hash, reason="Not a valid SHA256, SHA1 or MD5 hash"))
                consecutive_failures = 0
                continue
            except CLIENT_ERRORS as exc:
                # Never quote the client's own message: on some failures it
                # renders the whole request, headers included, back into the
                # exception text, which carries the key. Only the exception
                # kind is reported, in a message written here.
                errors.append(
                    HashLookupError(
                        hash=query_hash,
                        reason=f"PolySwarm did not return a result for this hash ({failure_kind(exc)})",
                    )
                )
                consecutive_failures += 1
                stop_reason = self._stop_reason(exc, consecutive_failures)
                if stop_reason is not None:
                    stopped_early = True
                    self.log(
                        f"{stop_reason} on request {queried} of {len(wanted)} ({failure_kind(exc)}). "
                        f"{len(wanted) - queried} hashes were not looked up, and the results gathered "
                        "so far are returned.",
                        level="warning",
                    )
                    break
                continue
            consecutive_failures = 0

            if found is None:
                not_found.append(query_hash)
                continue

            result = found
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
                            "The most recent scan has no verdict: its assertion window is still open, "
                            "or it closed without any engine returning a malicious or benign answer"
                        ),
                    )
                )
                continue

            results.append(self._build_verdict(query_hash, result, args.include_assertions))

        if not results and not not_found:
            reason = " PolySwarm rejected a lookup for usage limits." if rate_limited else ""
            if stopped_early:
                reason += " The run was stopped early because PolySwarm was not answering or refused the key."
            self.error(f"None of the supplied hashes could be looked up in PolySwarm.{reason}")
            return None

        response = SearchHashesResponse(
            results=results,
            not_found=not_found,
            errors=errors,
            requested_count=len(wanted),
            queried_count=queried,
            rate_limited=rate_limited,
        )

        # A hash that was never checked is unknown territory, not a clean
        # answer. That covers a usage limit cutting the run short and any
        # per-hash failure (server error, malformed hash, failed or still open
        # scan). Either one takes priority over detected/not detected, so a
        # non-empty errors list can never produce a clean verdict.
        if response.rate_limited or stopped_early or response.errors:
            self.set_output("partial", True)
        elif any(row.malicious_count > 0 for row in results):
            self.set_output("detected", True)
        else:
            self.set_output("not detected", True)

        return response.model_dump()

    @staticmethod
    def _stop_reason(exc: Exception, consecutive_failures: int) -> str | None:
        """Why a failed lookup should end the whole run, or None when only that hash is affected."""
        if status_of(exc) in AUTH_STATUSES:
            return "PolySwarm refused the API key"
        if isinstance(exc, TRANSPORT_ERRORS):
            return "PolySwarm could not be reached"
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            return f"{consecutive_failures} lookups in a row failed"
        return None

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
        tally = tally_assertions(result)

        return HashVerdict(
            hash=query_hash,
            sha256=result.sha256,
            malicious_count=tally.malicious_count,
            benign_count=tally.benign_count,
            total_count=tally.total_count,
            polyscore=result.polyscore,
            permalink=result.permalink,
            family=self._extract_family(result),
            assertions=tally.assertions if include_assertions else [],
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
