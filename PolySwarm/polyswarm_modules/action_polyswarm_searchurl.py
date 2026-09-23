"""Read only lookup of a URL, with no submission.

Two client methods can plausibly answer this: ``api.search_url`` and
``api.search_by_ioc``. ``search_url`` is what is chosen here, for a concrete
reason: it hits the ``/search/url`` endpoint and parses the response as an
``ArtifactInstance``, the same resource ``ScanUrl`` already reads for its own
existing-result lookup. That resource carries ``sha256``, ``assertions``,
``polyscore``, ``permalink`` and ``window_closed``, which is exactly the shape
``PolyswarmAction.is_complete`` and the verdict fields below need.
``search_by_ioc`` hits ``/ioc/search`` and parses its response as a bare
``IOC`` resource, which only wraps the raw JSON body and exposes none of
those fields as attributes: there is no assertion list to count, no
``window_closed`` to gate on, and no ``polyscore`` or ``permalink`` to report.
Building the same verdict shape from it would mean parsing undocumented JSON
by hand, which is worse than reusing the resource the scan action already
trusts. ``search_url`` also matches the artifact model the client itself
uses: a URL is a standalone artifact type on PolySwarm.
"""

from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from pydantic import BaseModel, Field
from requests import RequestException

from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.client import build_client
from polyswarm_modules.validators import invalid_url_reason

MISSING_RESULT: tuple[type[Exception], ...] = (
    ps_exceptions.NoResultsException,
    ps_exceptions.NotFoundException,
)
SEARCH_FAILURES: tuple[type[Exception], ...] = (
    ps_exceptions.PolyswarmException,
    RequestException,
)
ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})


class SearchUrlArguments(BaseModel):
    url: str = Field(..., description="The URL to search for")
    detect_threshold: int = Field(
        default=1,
        ge=1,
        description="How many malicious engine detections activate the detected branch",
    )


class AssertionResult(BaseModel):
    engine_name: str
    author_name: str
    verdict: bool | None


class SearchUrlResponse(BaseModel):
    found: bool = True
    sha256: str = ""
    permalink: str = ""
    polyscore: float | None = None
    malicious_count: int = 0
    benign_count: int = 0
    total_count: int = 0
    last_scanned: str = ""
    assertions: list[AssertionResult] = Field(default_factory=list)


class SearchUrl(PolyswarmAction):
    """Action to look up an existing PolySwarm verdict for a URL, without submitting it.

    This action only reads: it asks PolySwarm what it already knows about the
    URL and never calls submit, wait_for, or any sandbox method, so it spends
    no scanning quota and creates no activity on the account. Use ScanUrl
    instead when the URL should actually be submitted for a fresh verdict.

    The action activates one of three branches, the same shape as
    SearchHash: detected, not detected, or unknown when PolySwarm has never
    seen the URL. A result whose assertion window is still open carries no
    reportable verdict either, so PolyswarmAction.is_complete gates it the
    same way as an unseen URL: the playbook is left to decide whether to
    spend a scan next, rather than being told a partial result is clean.
    """

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        args = SearchUrlArguments(**arguments)

        reason = invalid_url_reason(args.url)
        if reason is not None:
            self.error(f"Refusing to search {reason}.")
            return None

        api = build_client(self.module.configuration)

        try:
            results = list(api.search_url(args.url))
        except MISSING_RESULT:
            # The client raises on 204 and 404 rather than returning an empty
            # list, and an unseen URL is the most common thing an analyst asks
            # about. Without this the playbook gets a Python traceback.
            results = []
        except SEARCH_FAILURES as exc:
            # Never quote the client's own message: it renders the request, which carries the key.
            self.error(f"PolySwarm did not search for the URL ({type(exc).__name__}).")
            return None

        # A result exists but has no verdict yet when its assertion window is
        # still open: it must not be served as detected or not detected, so
        # it is treated the same as never having been seen at all.
        result = results[0] if results and self.is_complete(results[0]) else None

        if result is None:
            self.set_output("unknown", True)
            return SearchUrlResponse(found=False).model_dump()

        response = self._build_response(result)
        self.set_output("detected" if response.malicious_count >= args.detect_threshold else "not detected", True)

        return response.model_dump()

    def _build_response(self, result: Any) -> SearchUrlResponse:
        # Only assertions inside the bloom mask are real answers from an
        # engine. An engine that abstained answers None, and it is neither
        # malicious nor benign: counting abstentions as benign inflates the
        # clean side of any ratio a customer writes a detection rule against.
        scored = [a for a in result.assertions if a.mask]

        assertions = [
            AssertionResult(
                engine_name=a.engine_name,
                author_name=a.author_name,
                verdict=a.verdict,
            )
            for a in scored
        ]

        return SearchUrlResponse(
            found=True,
            sha256=result.sha256,
            permalink=result.permalink,
            polyscore=result.polyscore,
            malicious_count=sum(1 for a in scored if a.verdict is True),
            benign_count=sum(1 for a in scored if a.verdict is False),
            total_count=len(scored),
            last_scanned=str(result.last_scanned),
            assertions=assertions,
        )
