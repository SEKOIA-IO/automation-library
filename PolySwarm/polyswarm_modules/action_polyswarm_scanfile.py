from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from polyswarm_api.api import PolyswarmAPI
from pydantic import BaseModel, Field

from polyswarm_modules.base import PolyswarmAction, sha256_handle
from polyswarm_modules.client import CLIENT_ERRORS, MISSING_RESULT, build_client, failure_kind
from polyswarm_modules.scan import DEFAULT_MAX_WAIT_SECONDS, MAX_WAIT_SECONDS_CEILING, MIN_WAIT_SECONDS, wait_for_scan
from polyswarm_modules.verdict import AssertionResult, tally_assertions


class ScanFileArguments(BaseModel):
    detect_threshold: int = Field(
        default=1,
        ge=1,
        description=(
            "How many malicious engine detections activate the detected branch. "
            "Default of 1 flags on any single detection."
        ),
    )
    file: str = Field(
        ...,
        description=(
            "Name of the file to scan, relative to the run data directory where Sekoia "
            "delivers it. The file is uploaded to PolySwarm's engine marketplace, which "
            "spends a scan unless a matching result already exists."
            " The upload to PolySwarm has no time limit of its own (a limitation of the PolySwarm client "
            "library), so a stalled network connection can hold the run until Sekoia's own action "
            "timeout stops it."
        ),
    )
    scan_config: str = Field(
        default="default",
        description=(
            "How long PolySwarm waits for engines to answer before returning a verdict: "
            "'default' is fastest; 'more-time' and 'most-time' wait longer so more engines "
            "can finish, at the cost of a slower playbook run.\n\n"
            "See [scan time windows](https://docs.polyswarm.io) for details."
        ),
    )
    force_rescan: bool = Field(
        default=False,
        description=(
            "Skip the check for an existing result and submit a new scan. This spends a "
            "scan even when PolySwarm already has a result for this file, so leave it off "
            "unless you need a fresh verdict."
        ),
    )
    max_wait_seconds: int = Field(
        default=DEFAULT_MAX_WAIT_SECONDS,
        ge=MIN_WAIT_SECONDS,
        le=MAX_WAIT_SECONDS_CEILING,
        description=(
            "How long to wait for the engines to finish a new scan, in seconds, capped at "
            f"{MAX_WAIT_SECONDS_CEILING}. Only applies when a new scan is submitted. If the engines have "
            "not finished by then the action stops with an error and the scan keeps running at "
            "PolySwarm, so look the result up again later."
        ),
    )


class ScanFileResponse(BaseModel):
    sha256: str
    sha1: str
    md5: str
    extended_type: str
    polyscore: float | None
    permalink: str
    malicious_count: int
    benign_count: int
    total_count: int
    failed: bool
    cached: bool
    assertions: list[AssertionResult]


class ScanFile(PolyswarmAction):
    """Action to submit a file to PolySwarm's engine marketplace for a fresh verdict.

    This is a scan: it spends scan quota and creates activity on the account.
    An existing result is reused unless force_rescan is set. For a free,
    read-only lookup against a hash already known, use SearchHash instead.
    """

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        args = ScanFileArguments(**arguments)

        file_path = self.resolve_data_file(args.file)
        if file_path is None:
            return None

        api = build_client(self.module.configuration)

        # Open through the path object rather than the built in open(): on the S3
        # file backend the path points into a bucket, which only the path object
        # knows how to read. The client accepts the open handle directly.
        try:
            handle = file_path.open("rb")
        except OSError:
            self.error("The file could not be read from the run data directory")
            return None

        with handle:
            cached: bool = False
            result = None

            if not args.force_rescan:
                try:
                    result = self._lookup_existing(api, handle)
                except CLIENT_ERRORS as exc:
                    # Never quote the client's own message: it renders the request, which carries the key.
                    self.error(f"PolySwarm did not look up an existing scan for the file ({failure_kind(exc)}).")
                    return None
                if result is not None:
                    cached = True
                    self.log(f"Found existing scan for {result.sha256}", level="info")

            if result is None:
                try:
                    # The client uploads the file with a plain request that carries no timeout and
                    # sits outside the retrying session, and this action cannot inject one without
                    # patching the library. The limitation is stated in the descriptor instead, and
                    # only the wait after the upload is bounded here.
                    instance = api.submit(handle, artifact_name=file_path.name, scan_config=args.scan_config)
                    result = wait_for_scan(api, instance, args.max_wait_seconds)
                except ps_exceptions.TimeoutException:
                    # The scan itself is not cancelled, only the wait for it, so it can still be read later.
                    self.error(
                        f"PolySwarm had not finished the file scan after {args.max_wait_seconds} seconds. "
                        "The scan is still running, look the result up again later."
                    )
                    return None
                except CLIENT_ERRORS as exc:
                    # Never quote the client's own message: it renders the request, which carries the key.
                    self.error(f"PolySwarm did not scan the file ({failure_kind(exc)}).")
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

    def _lookup_existing(self, api: PolyswarmAPI, handle: Any) -> Any:
        file_hash: str = sha256_handle(handle)
        try:
            results = list(api.search(file_hash))
            if results and self.is_complete(results[0]):
                return results[0]
        except MISSING_RESULT:
            pass
        return None

    def _build_response(self, result: Any, cached: bool) -> ScanFileResponse:
        tally = tally_assertions(result)

        return ScanFileResponse(
            sha256=result.sha256,
            sha1=result.sha1,
            md5=result.md5,
            extended_type=result.extended_type,
            polyscore=result.polyscore,
            permalink=result.permalink,
            malicious_count=tally.malicious_count,
            benign_count=tally.benign_count,
            total_count=tally.total_count,
            failed=result.failed,
            cached=cached,
            assertions=tally.assertions,
        )
