from unittest.mock import MagicMock, patch

import pytest
from polyswarm_api import exceptions as ps_exceptions

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_searchurl import SearchUrl


@pytest.fixture
def action(data_storage: str, module: PolyswarmModule) -> SearchUrl:
    return SearchUrl(module=module, data_path=data_storage)


def _make_assertion(*, engine_name: str, author_name: str, verdict: bool | None, mask: bool = True) -> MagicMock:
    a = MagicMock()
    a.engine_name = engine_name
    a.author_name = author_name
    a.verdict = verdict
    a.mask = mask
    return a


def _make_search_result(
    *,
    sha256: str = "bb" * 32,
    permalink: str = "https://polyswarm.network/scan/results/url-123",
    polyscore: float = 0.7,
    last_scanned: str = "2024-02-01T00:00:00Z",
    window_closed: bool = True,
    failed: bool = False,
    assertions: list[MagicMock] | None = None,
) -> MagicMock:
    if assertions is None:
        assertions = [
            _make_assertion(engine_name="PhishDetect", author_name="phishdetect", verdict=True),
            _make_assertion(engine_name="SafeBrowse", author_name="safebrowse", verdict=False),
        ]

    result = MagicMock()
    result.sha256 = sha256
    result.permalink = permalink
    result.polyscore = polyscore
    result.last_scanned = last_scanned
    result.window_closed = window_closed
    result.failed = failed
    result.assertions = assertions
    return result


@patch("polyswarm_modules.action_polyswarm_searchurl.build_client")
def test_uses_the_shared_retrying_client(
    mock_build_client: MagicMock, action: SearchUrl, module: PolyswarmModule
) -> None:
    """The action must build its client through build_client, not a bare PolyswarmAPI(), to get retries."""
    mock_build_client.return_value.search_url.return_value = [_make_search_result()]

    action.run({"url": "https://evil.example.com/payload"})

    mock_build_client.assert_called_once_with(module.configuration)


@patch("polyswarm_modules.action_polyswarm_searchurl.build_client")
def test_never_submits_or_waits(mock_build_client: MagicMock, action: SearchUrl) -> None:
    """This action is strictly read only: it must never call submit, wait_for, or any sandbox method."""
    mock_api = mock_build_client.return_value
    mock_api.search_url.return_value = [_make_search_result()]

    action.run({"url": "https://evil.example.com/payload"})

    mock_api.submit.assert_not_called()
    mock_api.wait_for.assert_not_called()
    called_methods = {call[0] for call in mock_api.method_calls}
    assert called_methods == {"search_url"}


@patch("polyswarm_modules.action_polyswarm_searchurl.build_client")
def test_a_detected_url_activates_the_detected_branch(mock_build_client: MagicMock, action: SearchUrl) -> None:
    mock_build_client.return_value.search_url.return_value = [_make_search_result()]

    response = action.run({"url": "https://evil.example.com/payload"})

    assert action._outputs == {"detected": True}
    assert response is not None
    assert response["found"] is True
    assert response["malicious_count"] == 1
    assert response["benign_count"] == 1
    assert response["sha256"] == "bb" * 32
    assert response["permalink"] == "https://polyswarm.network/scan/results/url-123"
    assert response["last_scanned"] == "2024-02-01T00:00:00Z"


@patch("polyswarm_modules.action_polyswarm_searchurl.build_client")
def test_a_clean_url_activates_the_not_detected_branch(mock_build_client: MagicMock, action: SearchUrl) -> None:
    assertions = [
        _make_assertion(engine_name="EngineA", author_name="a", verdict=False),
        _make_assertion(engine_name="EngineB", author_name="b", verdict=False),
    ]
    mock_build_client.return_value.search_url.return_value = [_make_search_result(assertions=assertions)]

    action.run({"url": "https://example.com"})

    assert action._outputs == {"not detected": True}


@patch("polyswarm_modules.action_polyswarm_searchurl.build_client")
def test_the_threshold_moves_the_branch(mock_build_client: MagicMock, action: SearchUrl) -> None:
    """A lone engine calling it malicious is the operator's judgement, not ours."""
    mock_build_client.return_value.search_url.return_value = [_make_search_result()]

    action.run({"url": "https://example.com", "detect_threshold": 99})

    assert action._outputs == {"not detected": True}


@patch("polyswarm_modules.action_polyswarm_searchurl.build_client")
def test_no_results_takes_the_unknown_branch(mock_build_client: MagicMock, action: SearchUrl) -> None:
    """An unseen URL is an ordinary outcome: the playbook routes it, it does not stop."""
    mock_build_client.return_value.search_url.return_value = []

    response = action.run({"url": "https://example.com"})

    assert response is not None
    assert response["found"] is False
    assert action.error_message is None
    assert action._outputs == {"unknown": True}


@patch("polyswarm_modules.action_polyswarm_searchurl.build_client")
def test_missing_result_exception_takes_the_unknown_branch(mock_build_client: MagicMock, action: SearchUrl) -> None:
    mock_build_client.return_value.search_url.side_effect = ps_exceptions.NoResultsException("404")

    response = action.run({"url": "https://example.com"})

    assert response is not None
    assert response["found"] is False
    assert action.error_message is None
    assert action._outputs == {"unknown": True}


@patch("polyswarm_modules.action_polyswarm_searchurl.build_client")
def test_open_assertion_window_is_not_served_as_a_verdict(mock_build_client: MagicMock, action: SearchUrl) -> None:
    """A result whose window is still open has no verdict yet and must not be reported as one."""
    pending = _make_search_result(window_closed=False)
    mock_build_client.return_value.search_url.return_value = [pending]

    response = action.run({"url": "https://example.com"})

    assert response is not None
    assert response["found"] is False
    assert action._outputs == {"unknown": True}


@patch("polyswarm_modules.action_polyswarm_searchurl.build_client")
def test_a_failed_result_is_not_served_as_a_verdict(mock_build_client: MagicMock, action: SearchUrl) -> None:
    failed = _make_search_result(failed=True)
    mock_build_client.return_value.search_url.return_value = [failed]

    response = action.run({"url": "https://example.com"})

    assert response is not None
    assert response["found"] is False
    assert action._outputs == {"unknown": True}


@patch("polyswarm_modules.action_polyswarm_searchurl.build_client")
def test_excludes_unmasked(mock_build_client: MagicMock, action: SearchUrl) -> None:
    assertions = [
        _make_assertion(engine_name="Active", author_name="active", verdict=True, mask=True),
        _make_assertion(engine_name="Inactive", author_name="inactive", verdict=False, mask=False),
    ]
    mock_build_client.return_value.search_url.return_value = [_make_search_result(assertions=assertions)]

    response = action.run({"url": "https://example.com"})

    assert response is not None
    assert len(response["assertions"]) == 1
    assert response["assertions"][0]["engine_name"] == "Active"


@patch("polyswarm_modules.action_polyswarm_searchurl.build_client")
def test_abstaining_engines_are_not_counted_as_benign(mock_build_client: MagicMock, action: SearchUrl) -> None:
    assertions = [
        _make_assertion(engine_name="Malicious", author_name="m", verdict=True),
        _make_assertion(engine_name="Abstained", author_name="a", verdict=None),
    ]
    mock_build_client.return_value.search_url.return_value = [_make_search_result(assertions=assertions)]

    response = action.run({"url": "https://example.com"})

    assert response is not None
    assert response["malicious_count"] == 1
    assert response["benign_count"] == 0
    assert response["total_count"] == 2


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/file",
        "javascript:alert(1)",
        "file:///etc/passwd",
        "example.com/payload",
        "",
    ],
)
@patch("polyswarm_modules.action_polyswarm_searchurl.build_client")
def test_refuses_a_non_http_scheme(mock_build_client: MagicMock, action: SearchUrl, url: str) -> None:
    response = action.run({"url": url})

    assert response is None
    assert action.error_message is not None
    assert "http or https" in action.error_message
    mock_build_client.assert_not_called()


@patch("polyswarm_modules.action_polyswarm_searchurl.build_client")
def test_lookup_failure_returns_none_without_quoting_the_client(
    mock_build_client: MagicMock, action: SearchUrl
) -> None:
    """A lookup failure must not surface the client's own message, which carries the key."""
    mock_api = mock_build_client.return_value
    secret_message = "test-api-key was rejected by https://api.polyswarm.network/v3"
    mock_api.search_url.side_effect = ps_exceptions.UsageLimitsExceededException(secret_message)

    response = action.run({"url": "https://example.com"})

    assert response is None
    assert action.error_message is not None
    assert secret_message not in action.error_message
