from unittest.mock import MagicMock

from requests.adapters import HTTPAdapter

from polyswarm_modules.client import RETRY_BACKOFF_MAX, install_retries
from tests.helpers import autospec_api


def _installed_retry() -> object:
    api = autospec_api()
    install_retries(api)
    mounted = {call.args[0]: call.args[1] for call in api.session.mount.call_args_list}
    adapter = mounted["https://"]
    assert isinstance(adapter, HTTPAdapter)
    return adapter.max_retries


def test_rate_limit_is_not_retried() -> None:
    retry = _installed_retry()

    assert 429 not in retry.status_forcelist  # type: ignore[attr-defined]
    assert not retry.is_retry("GET", 429, has_retry_after=True)  # type: ignore[attr-defined]


def test_retry_after_header_is_ignored_and_backoff_is_capped() -> None:
    retry = _installed_retry()

    assert retry.respect_retry_after_header is False  # type: ignore[attr-defined]
    assert retry.backoff_max == RETRY_BACKOFF_MAX <= 30  # type: ignore[attr-defined]
    # A 503 is still retried, but only for the capped backoff, never the header.
    assert retry.is_retry("GET", 503)  # type: ignore[attr-defined]


def test_post_is_never_retried() -> None:
    retry = _installed_retry()

    assert not retry.is_retry("POST", 503)  # type: ignore[attr-defined]


def test_missing_session_is_tolerated() -> None:
    api = MagicMock(spec=[])

    install_retries(api)
