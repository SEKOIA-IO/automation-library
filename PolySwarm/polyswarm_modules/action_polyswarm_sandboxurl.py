from typing import Any

from polyswarm_api.api import PolyswarmAPI
from pydantic import BaseModel, Field

from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.client import CLIENT_ERRORS, MISSING_RESULT, build_client, choose_vm_slug, failure_kind
from polyswarm_modules.sandbox import (
    DEFAULT_MAX_WAIT_SECONDS,
    MAX_WAIT_SECONDS_CEILING,
    SUBMIT_POLL_INTERVAL_CEILING,
    poll_until_terminal,
    report_url,
    validate_provider,
)
from polyswarm_modules.validators import invalid_url_reason


class SandboxUrlArguments(BaseModel):
    url: str = Field(..., description="The URL to detonate")
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


class SandboxUrlResponse(BaseModel):
    sandbox_task_id: str
    url: str
    sha256: str
    sandbox: str
    vm_slug: str
    status: str
    already_analysed: bool
    report_url: str


class SandboxUrl(PolyswarmAction):
    """Action to submit a URL to PolySwarm for sandbox detonation.

    Returns the task identity immediately rather than blocking for a
    verdict: the sandbox task id, the hash PolySwarm assigns the URL, the
    provider, the status at submission, and the URL where the finished
    report can be fetched. PolySwarm's SandboxCompleted trigger already
    exists to start a playbook when a detonation finishes, so the normal way
    to use this action is to submit here and let the trigger wake the next
    step, rather than holding a playbook run open for the fifteen minutes a
    real detonation can take. An optional wait argument is available for the
    interactive case, off by default and bounded to a short ceiling. Looks
    for an existing report for the same URL and provider first, so a
    resubmission does not spend a duplicate detonation, unless force says
    otherwise.
    """

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        args = SandboxUrlArguments(**arguments)

        reason = invalid_url_reason(args.url)
        if reason is not None:
            self.error(f"Refusing to detonate {reason}.")
            return None

        api = build_client(self.module.configuration)

        if not validate_provider(api, args.sandbox, self.log, self.error):
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
            existing = self._lookup_existing(api, args.url, args.sandbox)
            if existing is not None:
                self.log(f"Found existing sandbox report for {args.url} on {args.sandbox}", level="info")
                self.set_output("already analysed", True)
                return self._respond(api, existing, args, already_analysed=True).model_dump()

        task = self._submit(api, args)
        if task is None:
            return None

        if args.wait:
            task = poll_until_terminal(api, task, args.max_wait_seconds, SUBMIT_POLL_INTERVAL_CEILING, self.log)

        self.set_output("submitted", True)
        return self._respond(api, task, args, already_analysed=False).model_dump()

    def _lookup_existing(self, api: PolyswarmAPI, url: str, sandbox: str) -> Any:
        """Resolve the URL to the hash PolySwarm already assigned it, then check for a sandbox report.

        The sandbox task lookup is keyed by sha256, and a URL has no hash of
        its own until PolySwarm has processed it as an artifact once, so an
        existing scan is found through search_url first. Either step
        answering with nothing means there is nothing to reuse, not a
        failure, and both fall through to submitting a fresh detonation.
        """
        try:
            results = list(api.search_url(url))
        except MISSING_RESULT:
            return None
        except CLIENT_ERRORS as exc:
            self.log(
                f"Could not look up an existing artifact for the URL ({failure_kind(exc)}), "
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
                f"Could not check for an existing report ({failure_kind(exc)}), submitting a new one instead",
                level="warning",
            )
        return None

    def _submit(self, api: PolyswarmAPI, args: SandboxUrlArguments) -> Any:
        self.log(f"No existing report found, submitting a URL to sandbox {args.sandbox}", level="info")
        try:
            return api.sandbox_url(
                args.url,
                provider_slug=args.sandbox,
                vm_slug=args.vm_slug,
            )
        except CLIENT_ERRORS as exc:
            self.error(f"PolySwarm could not submit the URL to sandbox {args.sandbox} ({failure_kind(exc)}).")
            return None

    def _respond(
        self, api: PolyswarmAPI, task: Any, args: SandboxUrlArguments, already_analysed: bool
    ) -> SandboxUrlResponse:
        # vm_slug is not a field the API hands back on a sandbox task, so the
        # value requested for this run is echoed rather than read off task.
        community = self._as_text(getattr(task, "community", None)) or self.module.configuration.community
        return SandboxUrlResponse(
            sandbox_task_id=str(task.id),
            url=args.url,
            sha256=self._as_text(getattr(task, "sha256", None)) or "",
            sandbox=self._as_text(getattr(task, "sandbox", None)) or "",
            vm_slug=args.vm_slug,
            status=str(getattr(task, "status", "") or ""),
            already_analysed=already_analysed,
            report_url=report_url(api, str(task.id), community),
        )

    @staticmethod
    def _as_text(value: Any) -> str | None:
        if value is None:
            return None
        return str(value)
