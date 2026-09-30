from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from polyswarm_api.api import PolyswarmAPI
from polyswarm_api.resources import ArtifactType
from pydantic import BaseModel, Field
from requests import RequestException

from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.client import build_client
from polyswarm_modules.validators import invalid_url_reason

MISSING_RESULT: tuple[type[Exception], ...] = (
    ps_exceptions.NoResultsException,
    ps_exceptions.NotFoundException,
)
SCAN_FAILURES: tuple[type[Exception], ...] = (
    ps_exceptions.PolyswarmException,
    RequestException,
)
ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})


class ScanUrlArguments(BaseModel):
    detect_threshold: int = Field(
        default=1,
        ge=1,
        description=(
            "How many malicious engine detections activate the detected branch. "
            "Default of 1 flags on any single detection."
        ),
    )
    url: str = Field(
        ...,
        description=(
            "The URL to scan. Submitted to PolySwarm's engine marketplace, which spends "
            "a scan unless a matching result already exists."
        ),
    )
    scan_config: str = Field(
        default="more-time",
        description=(
            "How long PolySwarm waits for engines to answer before returning a verdict: "
            "'default' is fastest; 'more-time' and 'most-time' wait longer so more engines "
            "can finish, at the cost of a slower playbook run."
        ),
    )
    force_rescan: bool = Field(
        default=False,
        description=(
            "Skip the check for an existing result and submit a new scan. This spends a "
            "scan even when PolySwarm already has a result for this URL, so leave it off "
            "unless you need a fresh verdict."
        ),
    )


class AssertionResult(BaseModel):
    engine_name: str
    author_name: str
    verdict: bool | None


class ScanUrlResponse(BaseModel):
    sha256: str
    permalink: str
    polyscore: float | None
    extended_type: str
    malicious_count: int
    benign_count: int
    total_count: int
    failed: bool
    cached: bool
    assertions: list[AssertionResult]


class ScanUrl(PolyswarmAction):
    """Action to submit a URL to PolySwarm's engine marketplace for a fresh verdict.

    This is a scan: it spends scan quota and creates activity on the account.
    An existing result is reused unless force_rescan is set.
    """

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        args = ScanUrlArguments(**arguments)

        reason = invalid_url_reason(args.url)
        if reason is not None:
            self.error(f"Refusing to scan {reason}.")
            return None

        api = build_client(self.module.configuration)

        cached: bool = False
        result = None

        if not args.force_rescan:
            try:
                result = self._lookup_existing(api, args.url)
            except SCAN_FAILURES as exc:
                # Never quote the client's own message: it renders the request, which carries the key.
                self.error(f"PolySwarm did not look up an existing scan for the URL ({type(exc).__name__}).")
                return None
            if result is not None:
                cached = True
                self.log(f"Found existing scan for URL {args.url}", level="info")

        if result is None:
            try:
                instance = api.submit(
                    args.url,
                    artifact_type=ArtifactType.URL,
                    scan_config=args.scan_config,
                )
                result = api.wait_for(instance)
            except SCAN_FAILURES as exc:
                # Never quote the client's own message: it renders the request, which carries the key.
                self.error(f"PolySwarm did not scan the URL ({type(exc).__name__}).")
                return None
            if result.failed:
                self.error("PolySwarm reported the scan as failed, so there is no verdict")
                return None
            if not getattr(result, "window_closed", False):
                self.error("The assertion window is still open, so there is no verdict yet")
                return None

        response = self._build_response(result, cached)
        self.set_output("detected" if response.malicious_count >= args.detect_threshold else "not detected", True)

        return response.model_dump()

    def _lookup_existing(self, api: PolyswarmAPI, url: str) -> Any:
        try:
            results = list(api.search_url(url))
            if results and self.is_complete(results[0]):
                return results[0]
        except MISSING_RESULT:
            pass
        return None

    def _build_response(self, result: Any, cached: bool) -> ScanUrlResponse:
        # Only assertions inside the bloom mask are real answers from an engine.
        # An engine that abstained answers None, and it is neither malicious nor
        # benign: counting abstentions as benign inflates the clean side of any
        # ratio a customer writes a detection rule against.
        scored = [a for a in result.assertions if a.mask]

        assertions = [
            AssertionResult(
                engine_name=a.engine_name,
                author_name=a.author_name,
                verdict=a.verdict,
            )
            for a in scored
        ]

        return ScanUrlResponse(
            sha256=result.sha256,
            permalink=result.permalink,
            polyscore=result.polyscore,
            extended_type=result.extended_type,
            malicious_count=sum(1 for a in scored if a.verdict is True),
            benign_count=sum(1 for a in scored if a.verdict is False),
            total_count=len(scored),
            failed=result.failed,
            cached=cached,
            assertions=assertions,
        )
