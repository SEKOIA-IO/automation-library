import time
from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from pydantic import BaseModel, Field
from requests import RequestException

from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.client import build_client

MISSING_RESULT: tuple[type[Exception], ...] = (
    ps_exceptions.NoResultsException,
    ps_exceptions.NotFoundException,
)
CLIENT_ERRORS: tuple[type[Exception], ...] = (ps_exceptions.PolyswarmException, RequestException)

TERMINAL_STATUSES: frozenset[str] = frozenset({"SUCCEEDED", "FAILED"})
# Synthetic status for a hash and provider that has never had a sandbox task
# created for it at all, distinct from every real provider status.
NOT_FOUND_STATUS: str = "NOT_FOUND"

# A fast provider should not wait behind a slow one's interval, and a slow
# provider should not be hammered every few seconds for the whole wait, so
# the interval grows from a short first check up to an explicit ceiling.
INITIAL_POLL_INTERVAL: float = 5.0
POLL_BACKOFF_FACTOR: float = 2.0
POLL_INTERVAL_CEILING: float = 60.0


class ReportArguments(BaseModel):
    sha256: str = Field(..., description="SHA256 hash of the artifact to fetch a sandbox report for")
    sandbox: str = Field(default="cape", description="Sandbox provider slug (e.g. 'cape', 'triage')")
    max_wait_seconds: int = Field(
        default=0,
        ge=0,
        description=(
            "How long to wait for a detonation that is already running elsewhere to finish, in seconds. "
            "0, the default, does not wait: this reads the task's current status and returns immediately, "
            "which is why the SandboxCompleted trigger exists, so nobody has to sit here waiting. Polling "
            "backs off from a short first check up to a 60 second ceiling. This action never starts a "
            "detonation itself; submit one with SandboxFile, SandboxUrl or SandboxIp first."
        ),
    )


class ProcessEvidence(BaseModel):
    """One process the sandbox observed, normalised to the facts both providers carry."""

    pid: int | None = None
    parent_pid: int | None = None
    image: str = ""
    command_line: str = ""


class SandboxBehavior(BaseModel):
    """Typed slice of the sandbox report a playbook can act on without knowing either provider's schema.

    Every field here is read out of the raw report, never inferred or
    invented: a field a provider did not populate is absent or empty. CAPE
    and Hatching Triage disagree in shape for all of these, and each
    accessor in this module documents what was normalised to fill it.
    """

    behavior_signatures: list[str] = Field(default_factory=list)
    mitre_techniques: list[str] = Field(default_factory=list)
    contacted_hosts: list[str] = Field(default_factory=list)
    contacted_domains: list[str] = Field(default_factory=list)
    contacted_urls: list[str] = Field(default_factory=list)
    dropped_file_hashes: list[str] = Field(default_factory=list)
    processes: list[ProcessEvidence] = Field(default_factory=list)


class ReportResponse(BaseModel):
    sandbox_task_id: str
    sha256: str
    sandbox: str
    status: str
    # None means PolySwarm produced no verdict to report: nothing has been
    # detonated yet, a detonation failed, or a task is still processing. It
    # is never inferred to be False, since that would tell a playbook a
    # sample is clean when nobody has looked at it.
    malicious: bool | None
    behavior: SandboxBehavior
    report: Any
    sandbox_artifacts: list[dict[str, Any]]


def _unique(values: list[str]) -> list[str]:
    """Deduplicate while keeping the first occurrence, for lists built from nested loops."""
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def _signature_names(provider: str, report: dict[str, Any]) -> list[str]:
    """Signature and behaviour names PolySwarm's sandbox fired, normalised across providers.

    CAPE ships a flat, already deduplicated signature_names list. Triage has
    no equivalent: names live nested under static.signatures (static PE
    checks) and under each entry in targets[].signatures (behavioural,
    technique linked signatures), so both are walked and deduplicated here
    to land in the same shape CAPE gives for free.
    """
    if provider == "cape":
        return _unique([n for n in (report.get("signature_names") or []) if n])

    names: list[str] = []
    static = report.get("static") or {}
    for signature in static.get("signatures") or []:
        name = signature.get("name")
        if name:
            names.append(name)
    for target in report.get("targets") or []:
        for signature in target.get("signatures") or []:
            name = signature.get("name")
            if name:
                names.append(name)
    return _unique(names)


def _mitre_techniques(report: dict[str, Any]) -> list[str]:
    """MITRE ATT&CK technique identifiers, deduplicated.

    Both providers carry a top-level ttp list under the same key. Triage
    repeats an identifier once per signature that raised it, so a plain read
    would double count a single technique seen on several signatures.
    """
    return _unique([t for t in (report.get("ttp") or []) if t])


def _network_indicators(provider: str, report: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    """Contacted hosts, domains and URLs, normalised across providers.

    CAPE carries all three under report.network (hosts, domains, dns, http).
    Triage splits the same information across report.network (ips, flows)
    and report.requests (per domain request records). A URL is only ever
    populated when a provider actually captured one off the wire; on a
    TLS flow Triage did not decrypt, contacted_urls is legitimately empty
    even though contacted_domains carries the SNI.
    """
    hosts: list[str] = []
    domains: list[str] = []
    urls: list[str] = []
    network = report.get("network") or {}

    if provider == "cape":
        for host in network.get("hosts") or []:
            ip = host.get("ip")
            if ip:
                hosts.append(ip)
        for domain in network.get("domains") or []:
            name = domain.get("domain")
            if name:
                domains.append(name)
        for entry in network.get("dns") or []:
            request = entry.get("request")
            if request:
                domains.append(request)
        for entry in network.get("http") or []:
            uri = entry.get("uri") or entry.get("url")
            if uri:
                urls.append(uri)
    else:
        for ip_entry in network.get("ips") or []:
            ip = ip_entry.get("ip")
            if ip:
                hosts.append(ip)
        for flow in network.get("flows") or []:
            domain = flow.get("domain") or flow.get("tls_sni")
            if domain:
                domains.append(domain)
        for entry in report.get("requests") or []:
            domain = entry.get("domain")
            if domain:
                domains.append(domain)
            for http_entry in entry.get("http_request") or []:
                url = http_entry.get("url") or http_entry.get("uri")
                if url:
                    urls.append(url)

    return _unique(hosts), _unique(domains), _unique(urls)


def _dropped_file_hashes(provider: str, report: dict[str, Any]) -> list[str]:
    """Sha256 hashes of files the run wrote to disk.

    CAPE lists these under dropped. Triage lists everything the run wrote
    under dumped, which is broader than a CAPE drop (it also catches loaded
    modules and log files), but every entry that carries a sha256 is kept on
    the same reasoning CAPE uses: an analyst reading this field wants every
    file the sandbox pulled out of the run, not a claim about which of them
    are malicious.
    """
    key = "dropped" if provider == "cape" else "dumped"
    hashes = [entry.get("sha256") for entry in (report.get(key) or []) if entry.get("sha256")]
    return _unique(hashes)


def _processes(provider: str, report: dict[str, Any]) -> list[ProcessEvidence]:
    """Process and command line evidence, normalised across providers.

    CAPE nests the command line inside behavior.processes[].environ.
    CommandLine, with the parent id at parent_id and the binary path at
    module_path. Triage carries the same three facts flat, as cmd, ppid and
    image. Both are read into the same shape here.
    """
    processes: list[ProcessEvidence] = []

    if provider == "cape":
        behavior = report.get("behavior") or {}
        for proc in behavior.get("processes") or []:
            environ = proc.get("environ") or {}
            processes.append(
                ProcessEvidence(
                    pid=proc.get("process_id"),
                    parent_pid=proc.get("parent_id"),
                    image=proc.get("module_path") or "",
                    command_line=environ.get("CommandLine") or "",
                )
            )
    else:
        for proc in report.get("processes") or []:
            processes.append(
                ProcessEvidence(
                    pid=proc.get("pid"),
                    parent_pid=proc.get("ppid"),
                    image=proc.get("image") or "",
                    command_line=proc.get("cmd") or "",
                )
            )

    return processes


def _typed_behavior(provider: str, report: dict[str, Any]) -> SandboxBehavior:
    hosts, domains, urls = _network_indicators(provider, report)
    return SandboxBehavior(
        behavior_signatures=_signature_names(provider, report),
        mitre_techniques=_mitre_techniques(report),
        contacted_hosts=hosts,
        contacted_domains=domains,
        contacted_urls=urls,
        dropped_file_hashes=_dropped_file_hashes(provider, report),
        processes=_processes(provider, report),
    )


def _is_malicious(provider: str, report: dict[str, Any], config: dict[str, Any] | None) -> bool:
    """Decide the malicious / not malicious branch from the provider's own score.

    CAPE stores its overall verdict score on the task config as
    cape_malscore. Triage stores two: traige_analysis_score (the dynamic
    run; "traige" is the provider's own spelling, not a typo introduced
    here) and triage_static_score (static analysis only, sometimes the only
    one populated). When neither score is present, a report that named a
    malware family or fired a behaviour signature described the sample
    doing something, which is the same bar the score exists to capture, so
    that stands in instead.
    """
    config = config or {}
    score: float | None = None

    if provider == "cape":
        score = config.get("cape_malscore")
    elif provider == "triage":
        score = config.get("traige_analysis_score")
        if score is None:
            score = config.get("triage_static_score")

    if score is not None:
        return score > 0

    if report.get("malware_family"):
        return True
    return bool(_signature_names(provider, report))


class Report(PolyswarmAction):
    """Fetch the sandbox report already on file for a hash and provider.

    This action reads only: it submits nothing and spends no detonation.
    Activates one of three branches: malicious, not malicious, or no report
    available. The last covers every case that leaves nothing to report a
    verdict on: no sandbox task has ever been created for this hash and
    provider, a submitted detonation failed, or one is still running and
    either no wait was requested or the wait ceiling was reached first. To
    create a report, call SandboxFile, SandboxUrl or SandboxIp; this action
    never does.
    """

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        args = ReportArguments(**arguments)
        api = build_client(self.module.configuration)

        try:
            task = api.sandbox_task_latest(args.sha256, sandbox=args.sandbox)
        except MISSING_RESULT:
            task = None
        except CLIENT_ERRORS as exc:
            # Never quote the client's own message: it renders the request,
            # which carries the key.
            self.error(f"PolySwarm could not be reached to look up the sandbox report ({type(exc).__name__}).")
            return None

        if not task:
            return self._not_found_response(args)

        if args.max_wait_seconds > 0 and task.status not in TERMINAL_STATUSES:
            task = self._wait_for_running(api, task, args.max_wait_seconds)

        return self._respond(task)

    def _not_found_response(self, args: ReportArguments) -> dict[str, Any] | None:
        self.log(
            f"No sandbox task has ever been created for {args.sha256} on {args.sandbox}; "
            "call SandboxFile, SandboxUrl or SandboxIp to detonate it",
            level="info",
        )
        self.set_output("no report available", True)
        return ReportResponse(
            sandbox_task_id="",
            sha256=args.sha256,
            sandbox=args.sandbox,
            status=NOT_FOUND_STATUS,
            malicious=None,
            behavior=SandboxBehavior(),
            report=None,
            sandbox_artifacts=[],
        ).model_dump()

    def _wait_for_running(self, api: Any, task: Any, max_wait_seconds: int) -> Any:
        """Wait for a detonation that is already running elsewhere to reach a terminal status.

        This action never starts the detonation it waits on here: a
        playbook submits one with SandboxFile, SandboxUrl or SandboxIp, and
        this only polls the task that action created. The interval starts
        at INITIAL_POLL_INTERVAL and doubles each round, capped at
        POLL_INTERVAL_CEILING, so a fast provider gets an answer in seconds
        and a slow one is not polled every few seconds for the whole wait.
        The still-processing signal is the provider's own task status:
        anything outside TERMINAL_STATUSES is in progress.
        """
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

    def _respond(self, task: Any) -> dict[str, Any] | None:
        provider = (getattr(task, "sandbox", "") or "").lower()

        if task.status != "SUCCEEDED" or not task.report:
            if task.status == "FAILED":
                self.log(f"Sandbox task {task.id} failed to produce a report for {task.sha256}", level="warning")
            elif task.status != "SUCCEEDED":
                self.log(
                    f"Sandbox task {task.id} for {task.sha256} is still processing (status {task.status})",
                    level="warning",
                )
            else:
                self.log(f"Sandbox task {task.id} succeeded but PolySwarm returned no report content", level="warning")

            self.set_output("no report available", True)
            return ReportResponse(
                sandbox_task_id=str(task.id),
                sha256=task.sha256,
                sandbox=task.sandbox,
                status=task.status,
                malicious=None,
                behavior=SandboxBehavior(),
                report=task.report,
                sandbox_artifacts=[],
            ).model_dump()

        malicious = _is_malicious(provider, task.report, getattr(task, "config", None))
        self.set_output("malicious" if malicious else "not malicious", True)

        return ReportResponse(
            sandbox_task_id=str(task.id),
            sha256=task.sha256,
            sandbox=task.sandbox,
            status=task.status,
            malicious=malicious,
            behavior=_typed_behavior(provider, task.report),
            report=task.report,
            sandbox_artifacts=[
                {
                    "id": a.id,
                    "instance_id": a.instance_id,
                    "name": a.name,
                    "type": a.type,
                    "mimetype": a.mimetype,
                }
                for a in task.sandbox_artifacts
            ],
        ).model_dump()
