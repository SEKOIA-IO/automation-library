"""One place to build the PolySwarm client, with retries the library leaves off.

polyswarm_api ships a retrying session but sets the retry count to zero and only
lists 502 and 504 as retryable, so by default a transient gateway error or a
rate limit fails a whole playbook run. Retries are configured here instead, and
only for methods that are safe to repeat: a retried submission would detonate a
sample twice and bill for it twice, so POST is deliberately excluded.
"""

from typing import Any

from polyswarm_api.api import PolyswarmAPI
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_TIMEOUT: int = 60
RETRY_TOTAL: int = 3
RETRY_BACKOFF: float = 1.0
RETRY_ON: tuple[int, ...] = (429, 500, 502, 503, 504)
IDEMPOTENT_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})


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


def choose_vm_slug(api: Any, provider_slug: str, artifact_type: str) -> str | None:
    """Pick a sandbox image that can actually detonate this kind of artifact.

    Hardcoding an image is how this module shipped a default of
    win-10-build-19045, which does not exist: the real CAPE image is
    win-10-build-19041, so every detonation using the default would have been
    refused by the platform with "unknown sandbox provider or vm id". Images
    also differ by what they can take, and only some of them can open a URL at
    all, so the choice depends on the artifact as well as the provider.

    Returns None when the provider list cannot be read or offers nothing
    suitable, which the caller reports rather than guessing.
    """
    try:
        providers = list(api.sandbox_providers())
    except Exception:
        return None

    wanted = artifact_type.upper()
    for provider in providers:
        raw = getattr(provider, "json", None) or {}
        if (raw.get("slug") or getattr(provider, "slug", "")) != provider_slug:
            continue
        for name, vm in (raw.get("vms") or {}).items():
            if wanted in (vm.get("supported_artifact_types") or []):
                return str(vm.get("slug") or name)
    return None
