"""One place to build the PolySwarm client, with retries the library leaves off.

polyswarm_api ships a retrying session but sets the retry count to zero and only
lists 502 and 504 as retryable, so by default a transient gateway error or a
rate limit fails a whole playbook run. Retries are configured here instead, and
only for methods that are safe to repeat: a retried submission would detonate a
sample twice and bill for it twice, so POST is deliberately excluded.
"""

from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from polyswarm_api.api import PolyswarmAPI
from requests import RequestException
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_TIMEOUT: int = 60
RETRY_TOTAL: int = 3
RETRY_BACKOFF: float = 1.0
RETRY_ON: tuple[int, ...] = (429, 500, 502, 503, 504)
IDEMPOTENT_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})

# The client raises on 204 and 404 rather than returning an empty result, so
# "PolySwarm has nothing on this" arrives as an exception and is not an error.
MISSING_RESULT: tuple[type[Exception], ...] = (
    ps_exceptions.NoResultsException,
    ps_exceptions.NotFoundException,
)
# Everything the client or its transport can raise for a call that went wrong.
# A module level tuple rather than an inline one in each handler, so the
# formatter has no parenthesised exception list to rewrite.
CLIENT_ERRORS: tuple[type[Exception], ...] = (ps_exceptions.PolyswarmException, RequestException)


def build_client(configuration: Any, timeout: int = DEFAULT_TIMEOUT) -> PolyswarmAPI:
    """Build a PolySwarm client from module configuration, with retries enabled.

    The timeout is deliberately higher than the library default of 30 seconds:
    several PolySwarm endpoints answer slowly enough to trip it, and a timeout
    inside a playbook reads to an analyst as a broken integration.
    """
    api = PolyswarmAPI(
        key=configuration.apikey,
        community=configuration.community,
        timeout=timeout,
    )
    install_retries(api)
    return api


def install_retries(api: PolyswarmAPI) -> None:
    """Mount a retrying adapter on the client's session, for safe methods only."""
    session = getattr(api, "session", None)
    if session is None:
        return

    retry = Retry(
        total=RETRY_TOTAL,
        read=RETRY_TOTAL,
        connect=RETRY_TOTAL,
        status=RETRY_TOTAL,
        backoff_factor=RETRY_BACKOFF,
        status_forcelist=RETRY_ON,
        allowed_methods=IDEMPOTENT_METHODS,
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)


def failure_kind(exc: Exception) -> str:
    """The exception class and, when there is one, the HTTP status, for an error message.

    The status is what separates a bad key (401) from a spent quota (429) for
    an analyst reading the run. The exception text is deliberately left out:
    it can render the request back, and the request carries the query and the
    key. The polyswarm client keeps the status on the request it attaches to
    its own exceptions, and requests keeps it on the response, so both are
    read. Compared with None rather than tested for truth, because a requests
    Response is falsy for any 4xx or 5xx status.
    """
    carrier = getattr(exc, "response", None)
    if carrier is None:
        carrier = getattr(exc, "request", None)
    status = getattr(carrier, "status_code", None)
    kind = type(exc).__name__
    return f"{kind}, HTTP {status}" if isinstance(status, int) else kind
