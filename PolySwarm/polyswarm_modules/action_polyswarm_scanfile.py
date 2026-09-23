import hashlib
from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from polyswarm_api.api import PolyswarmAPI
from pydantic import BaseModel, Field
from requests import RequestException

from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.client import build_client

MISSING_RESULT: tuple[type[Exception], ...] = (
    ps_exceptions.NoResultsException,
    ps_exceptions.NotFoundException,
)
SCAN_FAILURES: tuple[type[Exception], ...] = (
    ps_exceptions.PolyswarmException,
    RequestException,
)


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


class AssertionResult(BaseModel):
    engine_name: str
    author_name: str
    verdict: bool | None


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


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


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

        cached: bool = False
        result = None

        if not args.force_rescan:
            try:
                result = self._lookup_existing(api, str(file_path))
            except SCAN_FAILURES as exc:
                # Never quote the client's own message: it renders the request, which carries the key.
                self.error(f"PolySwarm did not look up an existing scan for the file ({type(exc).__name__}).")
                return None
            if result is not None:
                cached = True
                self.log(f"Found existing scan for {result.sha256}", level="info")

        if result is None:
            try:
                instance = api.submit(str(file_path), scan_config=args.scan_config)
                result = api.wait_for(instance)
            except SCAN_FAILURES as exc:
                # Never quote the client's own message: it renders the request, which carries the key.
                self.error(f"PolySwarm did not scan the file ({type(exc).__name__}).")
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

    def _lookup_existing(self, api: PolyswarmAPI, file_path: str) -> Any:
        file_hash: str = _sha256_file(file_path)
        try:
            results = list(api.search(file_hash))
            if results and self.is_complete(results[0]):
                return results[0]
        except MISSING_RESULT:
            pass
        return None

    def _build_response(self, result: Any, cached: bool) -> ScanFileResponse:
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

        return ScanFileResponse(
            sha256=result.sha256,
            sha1=result.sha1,
            md5=result.md5,
            extended_type=result.extended_type,
            polyscore=result.polyscore,
            permalink=result.permalink,
            malicious_count=sum(1 for a in scored if a.verdict is True),
            benign_count=sum(1 for a in scored if a.verdict is False),
            total_count=len(scored),
            failed=result.failed,
            cached=cached,
            assertions=assertions,
        )
