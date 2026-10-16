"""Read only lookup of an IP address, with no submission.

An IP address has no artifact type of its own on PolySwarm: it is recorded as
a URL artifact, the same way ScanIp submits an IP through the URL scanning
endpoint. That makes ``api.search_url`` the natural read side of the same
model, and it is what is chosen here. ``api.search_by_ioc`` was read as well,
since it takes an ``ip`` argument directly and looked like the more literal
match. It hits ``/ioc/search`` and parses the response as a bare ``IOC``
resource, which only wraps the raw JSON body: no ``assertions`` list to
count, no ``window_closed`` to gate a verdict on, no ``polyscore`` or
``permalink`` attribute. ``search_url`` instead parses its response as an
``ArtifactInstance``, the same resource ScanIp already reads for its own
existing-result lookup, and it carries every field this action needs to
build the same verdict shape and to reuse PolyswarmAction.is_complete
unchanged.
"""

from typing import Any

from pydantic import BaseModel, Field

from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.client import CLIENT_ERRORS, MISSING_RESULT, build_client, failure_kind
from polyswarm_modules.coerce import as_text
from polyswarm_modules.validators import invalid_ip_reason
from polyswarm_modules.verdict import AssertionResult, tally_assertions


class SearchIpArguments(BaseModel):
    ip: str = Field(..., description="The IP address to search for")
    detect_threshold: int = Field(
        default=1,
        ge=1,
        description="How many malicious engine detections activate the detected branch",
    )


class SearchIpResponse(BaseModel):
    found: bool = True
    ip: str = ""
    sha256: str = ""
    permalink: str = ""
    polyscore: float | None = None
    malicious_count: int = 0
    benign_count: int = 0
    total_count: int = 0
    last_scanned: str = ""
    assertions: list[AssertionResult] = Field(default_factory=list)


class SearchIp(PolyswarmAction):
    """Action to look up an existing PolySwarm verdict for an IP address, without submitting it.

    This action only reads: it asks PolySwarm what it already knows about the
    IP and never calls submit, wait_for, or any sandbox method, so it spends
    no scanning quota and creates no activity on the account. Use ScanIp
    instead when the IP should actually be submitted for a fresh verdict.

    The action activates one of three branches, the same shape as
    SearchHash: detected, not detected, or unknown when PolySwarm has never
    seen the IP. A result whose assertion window is still open carries no
    reportable verdict either, so PolyswarmAction.is_complete gates it the
    same way as an unseen IP: the playbook is left to decide whether to
    spend a scan next, rather than being told a partial result is clean.
    """

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        args = SearchIpArguments(**arguments)

        reason = invalid_ip_reason(args.ip)
        if reason is not None:
            self.error(f"Refusing to search {reason}.")
            return None

        api = build_client(self.module.configuration)

        try:
            # Only the most recent result is read, so do not follow every page.
            first = next(iter(api.search_url(args.ip)), None)
        except MISSING_RESULT:
            # The client raises on 204 and 404 rather than returning an empty
            # list, and an unseen IP is the most common thing an analyst asks
            # about. Without this the playbook gets a Python traceback.
            first = None
        except CLIENT_ERRORS as exc:
            # Never quote the client's own message: it renders the request, which carries the key.
            self.error(f"PolySwarm did not search for the IP ({failure_kind(exc)}).")
            return None

        # A result exists but has no verdict yet when its assertion window is
        # still open: it must not be served as detected or not detected, so
        # it is treated the same as never having been seen at all.
        result = first if first is not None and self.is_complete(first) else None

        if result is None:
            self.set_output("unknown", True)
            return SearchIpResponse(found=False, ip=args.ip).model_dump()

        response = self._build_response(result, args.ip)
        self.set_output("detected" if response.malicious_count >= args.detect_threshold else "not detected", True)

        return response.model_dump()

    def _build_response(self, result: Any, ip: str) -> SearchIpResponse:
        tally = tally_assertions(result)

        return SearchIpResponse(
            found=True,
            ip=ip,
            sha256=result.sha256,
            permalink=result.permalink,
            polyscore=result.polyscore,
            malicious_count=tally.malicious_count,
            benign_count=tally.benign_count,
            total_count=tally.total_count,
            last_scanned=as_text(result.last_scanned),
            assertions=tally.assertions,
        )
