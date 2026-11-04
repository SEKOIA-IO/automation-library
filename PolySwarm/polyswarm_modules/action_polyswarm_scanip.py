from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from polyswarm_api.api import PolyswarmAPI
from polyswarm_api.resources import ArtifactType
from pydantic import BaseModel, Field

from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.client import CLIENT_ERRORS, MISSING_RESULT, build_client, failure_kind
from polyswarm_modules.coerce import as_text
from polyswarm_modules.scan import DEFAULT_MAX_WAIT_SECONDS, MAX_WAIT_SECONDS_CEILING, MIN_WAIT_SECONDS, wait_for_scan
from polyswarm_modules.validators import invalid_ip_reason
from polyswarm_modules.verdict import AssertionResult, has_verdict, tally_assertions


class ScanIpArguments(BaseModel):
    detect_threshold: int = Field(
        default=1,
        ge=1,
        description=(
            "How many malicious engine detections activate the detected branch. "
            "Default of 1 flags on any single detection."
        ),
    )
    ip: str = Field(
        ...,
        description=(
            "The IP address to scan. Submitted to PolySwarm's engine marketplace as a "
            "URL artifact, which spends a scan unless a matching result already exists. "
            "Private, loopback, link-local and other internal addresses are refused "
            "rather than submitted."
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
            "scan even when PolySwarm already has a result for this IP address, so leave "
            "it off unless you need a fresh verdict."
        ),
    )
    max_wait_seconds: int = Field(
        default=DEFAULT_MAX_WAIT_SECONDS,
        ge=MIN_WAIT_SECONDS,
        le=MAX_WAIT_SECONDS_CEILING,
        description=(
            "How long to wait for the engines to finish a new scan, in seconds, from "
            f"{MIN_WAIT_SECONDS} to {MAX_WAIT_SECONDS_CEILING}. A larger or smaller value is rejected with a "
            "validation error. Only applies when a new scan is submitted. The wait can run past this by one "
            "status check, about a minute at worst. If the engines have not finished by then the action stops "
            "with an error and the scan keeps running at PolySwarm, so look the result up again later."
        ),
    )


class ScanIpResponse(BaseModel):
    ip: str
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


class ScanIp(PolyswarmAction):
    """Action to submit an IP address to PolySwarm's engine marketplace for a fresh verdict.

    This is a scan: it spends scan quota and creates activity on the account.
    An existing result is reused unless force_rescan is set. PolySwarm has no
    separate IP endpoint, so the address is submitted as a URL artifact and
    the engines answer on it directly.
    """

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        args = ScanIpArguments(**arguments)

        reason = invalid_ip_reason(args.ip)
        if reason is not None:
            self.error(f"Refusing to scan {reason}.")
            return None

        api = build_client(self.module.configuration)

        cached: bool = False
        result = None

        if not args.force_rescan:
            try:
                result = self._lookup_existing(api, args.ip)
            except CLIENT_ERRORS as exc:
                # Never quote the client's own message: it renders the request, which carries the key.
                self.error(f"PolySwarm did not look up an existing scan for the IP ({failure_kind(exc)}).")
                return None
            if result is not None:
                cached = True
                self.log(f"Found existing scan for IP {args.ip}", level="info")

        if result is None:
            try:
                instance = api.submit(
                    args.ip,
                    artifact_type=ArtifactType.URL,
                    scan_config=args.scan_config,
                )
                result = wait_for_scan(api, instance, args.max_wait_seconds)
            except ps_exceptions.TimeoutException:
                # The scan itself is not cancelled, only the wait for it, so it can still be read later.
                self.error(
                    f"PolySwarm had not finished the IP scan after {args.max_wait_seconds} seconds. "
                    "The scan is still running, look the result up again later."
                )
                return None
            except CLIENT_ERRORS as exc:
                # Never quote the client's own message: it renders the request, which carries the key.
                self.error(f"PolySwarm did not scan the IP ({failure_kind(exc)}).")
                return None
            if result.failed:
                self.error("PolySwarm reported the scan as failed, so there is no verdict")
                return None
            if not getattr(result, "window_closed", False):
                self.error("The assertion window is still open, so there is no verdict yet")
                return None

        response = self._build_response(result, args.ip, cached)
        if not has_verdict(result):
            # The window closed but no engine gave a malicious or benign answer, so nobody looked at this
            # artifact. The body is still returned for the playbook, on a branch that is not "not detected".
            self.set_output("unknown", True)
            return response.model_dump()
        self.set_output("detected" if response.malicious_count >= args.detect_threshold else "not detected", True)

        return response.model_dump()

    def _lookup_existing(self, api: PolyswarmAPI, ip: str) -> Any:
        try:
            first = next(iter(api.search_url(ip)), None)
            if first is not None and self.is_complete(first):
                return first
        except MISSING_RESULT:
            pass
        return None

    def _build_response(self, result: Any, ip: str, cached: bool) -> ScanIpResponse:
        tally = tally_assertions(result)

        return ScanIpResponse(
            ip=ip,
            sha256=as_text(result.sha256),
            permalink=as_text(result.permalink),
            polyscore=result.polyscore,
            extended_type=as_text(result.extended_type),
            malicious_count=tally.malicious_count,
            benign_count=tally.benign_count,
            total_count=tally.total_count,
            failed=bool(result.failed),
            cached=cached,
            assertions=tally.assertions,
        )
