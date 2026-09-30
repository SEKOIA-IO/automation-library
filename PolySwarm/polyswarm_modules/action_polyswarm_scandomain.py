import re
from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from polyswarm_api.api import PolyswarmAPI
from polyswarm_api.resources import ArtifactType
from pydantic import BaseModel, Field
from requests import RequestException

from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.client import build_client
from polyswarm_modules.validators import invalid_domain_reason

MISSING_RESULT: tuple[type[Exception], ...] = (
    ps_exceptions.NoResultsException,
    ps_exceptions.NotFoundException,
)
SCAN_FAILURES: tuple[type[Exception], ...] = (
    ps_exceptions.PolyswarmException,
    RequestException,
)

# A label is one to 63 characters of letters, digits and hyphens, and cannot
# start or end with a hyphen. A hostname is one or more labels joined by dots.
_HOSTNAME_LABEL = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$")


class ScanDomainArguments(BaseModel):
    detect_threshold: int = Field(
        default=1,
        ge=1,
        description=(
            "How many malicious engine detections activate the detected branch. "
            "Default of 1 flags on any single detection."
        ),
    )
    domain: str = Field(
        ...,
        description=(
            "The domain to scan, for example example.com. Submitted to PolySwarm's "
            "engine marketplace as a URL artifact, which spends a scan unless a matching "
            "result already exists."
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
            "scan even when PolySwarm already has a result for this domain, so leave it "
            "off unless you need a fresh verdict."
        ),
    )


class AssertionResult(BaseModel):
    engine_name: str
    author_name: str
    verdict: bool | None


class ScanDomainResponse(BaseModel):
    domain: str
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


class ScanDomain(PolyswarmAction):
    """Action to submit a domain to PolySwarm's engine marketplace for a fresh verdict.

    This is a scan: it spends scan quota and creates activity on the account.
    An existing result is reused unless force_rescan is set. PolySwarm has no
    separate domain endpoint: a bare domain is submitted as a URL artifact and
    the engines answer on it directly, verified against the live service. The
    action exists as its own step because a playbook author looking for domain
    reputation should not have to know that.
    """

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        args = ScanDomainArguments(**arguments)

        reason = invalid_domain_reason(args.domain)
        if reason is not None:
            self.error(f"Refusing to scan {reason}.")
            return None

        api = build_client(self.module.configuration)

        cached: bool = False
        result = None

        if not args.force_rescan:
            try:
                result = self._lookup_existing(api, args.domain)
            except SCAN_FAILURES as exc:
                # Never quote the client's own message: it renders the request, which carries the key.
                self.error(f"PolySwarm did not look up an existing scan for the domain ({type(exc).__name__}).")
                return None
            if result is not None:
                cached = True
                self.log(f"Found existing scan for domain {args.domain}", level="info")

        if result is None:
            try:
                instance = api.submit(
                    args.domain,
                    artifact_type=ArtifactType.URL,
                    scan_config=args.scan_config,
                )
                result = api.wait_for(instance)
            except SCAN_FAILURES as exc:
                # Never quote the client's own message: it renders the request, which carries the key.
                self.error(f"PolySwarm did not scan the domain ({type(exc).__name__}).")
                return None
            if result.failed:
                self.error("PolySwarm reported the scan as failed, so there is no verdict")
                return None
            if not getattr(result, "window_closed", False):
                self.error("The assertion window is still open, so there is no verdict yet")
                return None

        response = self._build_response(result, args.domain, cached)
        self.set_output("detected" if response.malicious_count >= args.detect_threshold else "not detected", True)

        return response.model_dump()

    def _lookup_existing(self, api: PolyswarmAPI, domain: str) -> Any:
        try:
            results = list(api.search_url(domain))
            if results and self.is_complete(results[0]):
                return results[0]
        except MISSING_RESULT:
            pass
        return None

    def _build_response(self, result: Any, domain: str, cached: bool) -> ScanDomainResponse:
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

        return ScanDomainResponse(
            domain=domain,
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
