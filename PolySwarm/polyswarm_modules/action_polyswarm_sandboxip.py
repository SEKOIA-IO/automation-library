import time
from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from polyswarm_api.api import PolyswarmAPI
from pydantic import BaseModel, Field
from requests import RequestException

from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.client import build_client, choose_vm_slug
from polyswarm_modules.validators import invalid_ip_reason

MISSING_RESULT: tuple[type[Exception], ...] = (
    ps_exceptions.NoResultsException,
    ps_exceptions.NotFoundException,
)
CLIENT_ERRORS: tuple[type[Exception], ...] = (ps_exceptions.PolyswarmException, RequestException)

TERMINAL_STATUSES: frozenset[str] = frozenset({"SUCCEEDED", "FAILED"})

# Short first check, doubling up to a low ceiling: this wait is for an
# analyst watching the run, not the batch style poll a scheduled playbook
# would tolerate.
INITIAL_POLL_INTERVAL: float = 5.0
POLL_BACKOFF_FACTOR: float = 2.0
POLL_INTERVAL_CEILING: float = 30.0
DEFAULT_MAX_WAIT_SECONDS: int = 60
# Hard ceiling. Blocking a playbook run for fifteen minutes is the behaviour
# this action family replaces, so even an analyst who asks to wait cannot
# push it past five minutes; the SandboxCompleted trigger is the way to
# learn about anything slower than that.
MAX_WAIT_SECONDS_CEILING: int = 300

SANDBOX_TASK_ENDPOINT: str = "/sandbox/sandboxtask"

# The scheme used to turn an IP into the URL that actually gets detonated.
# https would just as often fail a handshake against a bare address with no
# certificate, so http is the one PolySwarm's sandbox is most likely to get
# an answer from when anything is listening at all.
DETONATION_SCHEME: str = "http"


def _ip_to_target(ip: str) -> str:
    """Turn an IP into the URL PolySwarm's sandbox actually browses to.

    PolySwarm has no IP detonation, so an IP is detonated by turning it into
    a URL first. An IPv6 address is bracketed the way a URL requires it.
    """
    host = f"[{ip}]" if ":" in ip else ip
    return f"{DETONATION_SCHEME}://{host}/"


def _report_url(api: PolyswarmAPI, task_id: str, community: str | None) -> str:
    """The API URL the PolySwarm client itself calls to read this task, matching the trigger's vocabulary."""
    base = f"{api.uri}{SANDBOX_TASK_ENDPOINT}?sandbox_task_id={task_id}"
    if community:
        return f"{base}&community={community}"
    return base


class SandboxIpArguments(BaseModel):
    ip: str = Field(..., description="The IP address to detonate")
    sandbox: str = Field(default="cape", description="Sandbox provider slug (e.g. 'cape', 'triage')")
    vm_slug: str = Field(
        default="",
        description=(
            "Sandbox image to detonate in. Leave empty and PolySwarm picks one that can take this "
            "kind of artifact, which is the safe choice because the available images change"
        ),
    )
    force: bool = Field(
        default=False,
        description="Skip the existing report lookup and submit a fresh detonation even when one is already available",
    )
    wait: bool = Field(
        default=False,
        description="Block until the detonation reaches a terminal status before returning, for interactive use. "
        "Off by default: the SandboxCompleted trigger already exists to start a playbook when a detonation "
        "finishes, so the normal path is to submit here and let the trigger wake the next step instead of "
        "holding this run open.",
    )
    max_wait_seconds: int = Field(
        default=DEFAULT_MAX_WAIT_SECONDS,
        ge=1,
        le=MAX_WAIT_SECONDS_CEILING,
        description="Only used when wait is enabled. Upper bound on how long to block for a terminal status, "
        "in seconds, capped at 300 regardless of the value supplied",
    )


class SandboxIpResponse(BaseModel):
    sandbox_task_id: str
    ip: str
    target: str
    sha256: str
    sandbox: str
    vm_slug: str
    status: str
    already_analysed: bool
    report_url: str


class SandboxIp(PolyswarmAction):
    """Action to detonate an IP address in PolySwarm's sandbox by converting it to a URL first.

    PolySwarm has no IP detonation: this action turns the address into a URL
    (http://<ip>/) and detonates that instead. The response carries the
    exact target that was actually detonated, so an analyst reading the
    result understands why it names a URL rather than the IP that was asked
    for. An address with no web service listening on it will usually
    detonate to very little: expect a mostly empty report unless something
    answers on the port the sandbox connects to. Loopback, link-local,
    private and reserved addresses are refused, using the same wording
    ScanIp uses, rather than sent to PolySwarm's public community.

    Returns the task identity immediately rather than blocking for a
    verdict: the sandbox task id, the hash PolySwarm assigns the target, the
    provider, the status at submission, and the URL where the finished
    report can be fetched. PolySwarm's SandboxCompleted trigger already
    exists to start a playbook when a detonation finishes, so the normal way
    to use this action is to submit here and let the trigger wake the next
    step, rather than holding a playbook run open for the fifteen minutes a
    real detonation can take. An optional wait argument is available for the
    interactive case, off by default and bounded to a short ceiling. Looks
    for an existing report for the same target and provider first, so a
    resubmission does not spend a duplicate detonation, unless force says
    otherwise.
    """

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        args = SandboxIpArguments(**arguments)

        reason = invalid_ip_reason(args.ip)
        if reason is not None:
            self.error(f"Refusing to detonate {reason}.")
            return None

        target = _ip_to_target(args.ip)

        api = build_client(self.module.configuration)

        if not self._validate_provider(api, args.sandbox):
            return None

        resolved_vm = args.vm_slug or choose_vm_slug(api, args.sandbox, "URL")

        if not resolved_vm:
            self.error(
                f"PolySwarm has no sandbox image for {args.sandbox} that can detonate this artifact. "
                "Name one explicitly, or check the provider."
            )

            return None

        args.vm_slug = resolved_vm

        if not args.force:
            existing = self._lookup_existing(api, target, args.sandbox)
            if existing is not None:
                self.log(f"Found existing sandbox report for {target} on {args.sandbox}", level="info")
                self.set_output("already analysed", True)
                return self._respond(api, existing, args, target, already_analysed=True).model_dump()

        task = self._submit(api, target, args)
        if task is None:
            return None

        if args.wait:
            task = self._poll_until_wait_ceiling(api, task, args.max_wait_seconds)

        self.set_output("submitted", True)
        return self._respond(api, task, args, target, already_analysed=False).model_dump()

    def _validate_provider(self, api: PolyswarmAPI, sandbox: str) -> bool:
        """True when the provider checks out, or the check could not be made and the value is trusted instead."""
        try:
            providers = list(api.sandbox_providers())
        except CLIENT_ERRORS as exc:
            self.log(
                f"Could not validate the sandbox provider against PolySwarm's provider list "
                f"({type(exc).__name__}), trusting the configured value",
                level="warning",
            )
            return True

        slugs = {getattr(p, "slug", "") for p in providers if getattr(p, "slug", "")}
        if slugs and sandbox not in slugs:
            self.error(
                f"'{sandbox}' is not a sandbox provider PolySwarm currently offers. "
                f"Known providers: {', '.join(sorted(slugs))}."
            )
            return False
        return True

    def _lookup_existing(self, api: PolyswarmAPI, target: str, sandbox: str) -> Any:
        """Resolve the detonated target to the hash PolySwarm already assigned it, then check for a sandbox report.

        The sandbox task lookup is keyed by sha256, and the target has no
        hash of its own until PolySwarm has processed it as an artifact
        once, so an existing scan is found through search_url first. Either
        step answering with nothing means there is nothing to reuse, not a
        failure, and both fall through to submitting a fresh detonation.
        """
        try:
            results = list(api.search_url(target))
        except MISSING_RESULT:
            return None
        except CLIENT_ERRORS as exc:
            self.log(
                f"Could not look up an existing artifact for the target ({type(exc).__name__}), "
                "submitting a new detonation instead",
                level="warning",
            )
            return None

        if not results:
            return None
        sha256 = str(getattr(results[0], "sha256", "") or "")
        if not sha256:
            return None

        try:
            task = api.sandbox_task_latest(sha256, sandbox=sandbox)
            if task and task.report:
                return task
        except MISSING_RESULT:
            pass
        except CLIENT_ERRORS as exc:
            self.log(
                f"Could not check for an existing report ({type(exc).__name__}), submitting a new one instead",
                level="warning",
            )
        return None

    def _submit(self, api: PolyswarmAPI, target: str, args: SandboxIpArguments) -> Any:
        self.log(f"No existing report found, submitting {target} to sandbox {args.sandbox}", level="info")
        try:
            return api.sandbox_url(
                target,
                provider_slug=args.sandbox,
                vm_slug=args.vm_slug,
            )
        except CLIENT_ERRORS as exc:
            self.error(f"PolySwarm could not submit {target} to sandbox {args.sandbox} ({type(exc).__name__}).")
            return None

    def _poll_until_wait_ceiling(self, api: PolyswarmAPI, task: Any, max_wait_seconds: int) -> Any:
        """Poll a sandbox task until it reaches a terminal status or the wait ceiling, whichever comes first."""
        deadline = time.monotonic() + max_wait_seconds
        interval = INITIAL_POLL_INTERVAL

        while task.status not in TERMINAL_STATUSES:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(interval, remaining))
            interval = min(interval * POLL_BACKOFF_FACTOR, POLL_INTERVAL_CEILING)
            try:
                task = api.sandbox_task_status(task.id)
            except CLIENT_ERRORS as exc:
                self.log(f"Sandbox status check failed ({type(exc).__name__}), retrying", level="warning")

        return task

    def _respond(
        self,
        api: PolyswarmAPI,
        task: Any,
        args: SandboxIpArguments,
        target: str,
        already_analysed: bool,
    ) -> SandboxIpResponse:
        # vm_slug is not a field the API hands back on a sandbox task, so the
        # value requested for this run is echoed rather than read off task.
        community = self._as_text(getattr(task, "community", None)) or self.module.configuration.community
        return SandboxIpResponse(
            sandbox_task_id=str(task.id),
            ip=args.ip,
            target=target,
            sha256=self._as_text(getattr(task, "sha256", None)) or "",
            sandbox=self._as_text(getattr(task, "sandbox", None)) or "",
            vm_slug=args.vm_slug,
            status=str(getattr(task, "status", "") or ""),
            already_analysed=already_analysed,
            report_url=_report_url(api, str(task.id), community),
        )

    @staticmethod
    def _as_text(value: Any) -> str | None:
        if value is None:
            return None
        return str(value)
