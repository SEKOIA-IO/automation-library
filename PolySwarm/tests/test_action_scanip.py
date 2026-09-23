from unittest.mock import MagicMock, patch

import pytest
from polyswarm_api import exceptions as ps_exceptions
from polyswarm_api.resources import ArtifactType

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_scanip import ScanIp


@pytest.fixture
def action(data_storage: str, module: PolyswarmModule) -> ScanIp:
    return ScanIp(module=module, data_path=data_storage)


def _make_assertion(*, engine_name: str, author_name: str, verdict: bool, mask: bool = True) -> MagicMock:
    a = MagicMock()
    a.engine_name = engine_name
    a.author_name = author_name
    a.verdict = verdict
    a.mask = mask
    return a


def _make_scan_result(
    *,
    sha256: str = "cc" * 32,
    permalink: str = "https://polyswarm.network/scan/results/ip-123",
    polyscore: float = 0.6,
    extended_type: str = "URL",
    failed: bool = False,
    assertions: list[MagicMock] | None = None,
) -> MagicMock:
    if assertions is None:
        assertions = [
            _make_assertion(engine_name="EngineA", author_name="engine_a", verdict=True),
            _make_assertion(engine_name="EngineB", author_name="engine_b", verdict=False),
        ]

    result = MagicMock()
    result.sha256 = sha256
    result.permalink = permalink
    result.polyscore = polyscore
    result.extended_type = extended_type
    result.failed = failed
    result.assertions = assertions
    result.malicious_assertions = [a for a in assertions if a.mask and a.verdict]
    result.benign_assertions = [a for a in assertions if a.mask and not a.verdict]
    result.valid_assertions = [a for a in assertions if a.mask]
    return result


@patch("polyswarm_modules.action_polyswarm_scanip.build_client")
def test_returns_cached_when_existing(mock_build_client: MagicMock, action: ScanIp) -> None:
    existing = _make_scan_result()
    mock_build_client.return_value.search_url.return_value = [existing]

    response = action.run({"ip": "1.2.3.4"})

    mock_build_client.return_value.search_url.assert_called_once_with("1.2.3.4")
    mock_build_client.return_value.submit.assert_not_called()
    assert response["cached"] is True
    assert response["ip"] == "1.2.3.4"


@patch("polyswarm_modules.action_polyswarm_scanip.build_client")
def test_submits_when_no_existing(mock_build_client: MagicMock, action: ScanIp) -> None:
    mock_api = mock_build_client.return_value
    mock_api.search_url.return_value = []
    mock_instance = MagicMock()
    mock_api.submit.return_value = mock_instance
    mock_api.wait_for.return_value = _make_scan_result()

    response = action.run({"ip": "5.6.7.8"})

    mock_api.submit.assert_called_once_with(
        "5.6.7.8",
        artifact_type=ArtifactType.URL,
        scan_config="more-time",
    )
    mock_api.wait_for.assert_called_once_with(mock_instance)
    assert response["cached"] is False


@patch("polyswarm_modules.action_polyswarm_scanip.build_client")
def test_force_rescan_skips_lookup(mock_build_client: MagicMock, action: ScanIp) -> None:
    mock_api = mock_build_client.return_value
    mock_api.submit.return_value = MagicMock()
    mock_api.wait_for.return_value = _make_scan_result()

    response = action.run({"ip": "1.2.3.4", "force_rescan": True})

    mock_api.search_url.assert_not_called()
    mock_api.submit.assert_called_once()
    assert response["cached"] is False


@patch("polyswarm_modules.action_polyswarm_scanip.build_client")
def test_submits_when_existing_failed(mock_build_client: MagicMock, action: ScanIp) -> None:
    failed = _make_scan_result(failed=True)
    mock_api = mock_build_client.return_value
    mock_api.search_url.return_value = [failed]
    mock_api.submit.return_value = MagicMock()
    mock_api.wait_for.return_value = _make_scan_result()

    response = action.run({"ip": "1.2.3.4"})

    mock_api.submit.assert_called_once()
    assert response["cached"] is False


@patch("polyswarm_modules.action_polyswarm_scanip.build_client")
def test_excludes_unmasked(mock_build_client: MagicMock, action: ScanIp) -> None:
    assertions = [
        _make_assertion(engine_name="Active", author_name="active", verdict=True, mask=True),
        _make_assertion(engine_name="Inactive", author_name="inactive", verdict=False, mask=False),
    ]
    mock_build_client.return_value.search_url.return_value = []
    mock_build_client.return_value.submit.return_value = MagicMock()
    mock_build_client.return_value.wait_for.return_value = _make_scan_result(assertions=assertions)

    response = action.run({"ip": "1.2.3.4"})

    assert len(response["assertions"]) == 1
    assert response["assertions"][0]["engine_name"] == "Active"


@patch("polyswarm_modules.action_polyswarm_scanip.build_client")
def test_detections_activate_the_detected_branch(mock_build_client: MagicMock, action: ScanIp) -> None:
    """The branch is what a playbook author wires on the canvas, so it follows the counts."""
    mock_api = mock_build_client.return_value
    mock_api.search_url.return_value = []
    mock_api.submit.return_value = MagicMock()
    mock_api.wait_for.return_value = _make_scan_result()

    action.run({"ip": "8.8.8.8"})

    assert action._outputs == {"detected": True}


@patch("polyswarm_modules.action_polyswarm_scanip.build_client")
def test_the_threshold_moves_the_branch(mock_build_client: MagicMock, action: ScanIp) -> None:
    """A lone engine calling it malicious is the operator's judgement, not ours."""
    mock_api = mock_build_client.return_value
    mock_api.search_url.return_value = []
    mock_api.submit.return_value = MagicMock()
    mock_api.wait_for.return_value = _make_scan_result()

    action.run({"ip": "8.8.8.8", "detect_threshold": 99})

    assert action._outputs == {"not detected": True}


@patch("polyswarm_modules.action_polyswarm_scanip.build_client")
def test_uses_the_shared_retrying_client(
    mock_build_client: MagicMock, action: ScanIp, module: PolyswarmModule
) -> None:
    """The action must build its client through build_client, not a bare PolyswarmAPI(), to get retries."""
    mock_api = mock_build_client.return_value
    mock_api.search_url.return_value = []
    mock_api.submit.return_value = MagicMock()
    mock_api.wait_for.return_value = _make_scan_result()

    action.run({"ip": "8.8.8.8"})

    mock_build_client.assert_called_once_with(module.configuration)


@pytest.mark.parametrize(
    "ip",
    [
        "192.168.1.1",  # private
        "10.0.0.1",  # private
        "127.0.0.1",  # loopback
        "169.254.1.1",  # link-local
        "0.0.0.0",  # reserved
        "::1",  # IPv6 loopback
        "fe80::1",  # IPv6 link-local
        "fc00::1",  # IPv6 unique local (private)
    ],
)
@patch("polyswarm_modules.action_polyswarm_scanip.build_client")
def test_refuses_non_public_addresses(mock_build_client: MagicMock, action: ScanIp, ip: str) -> None:
    response = action.run({"ip": ip})

    assert response is None
    assert action.error_message is not None
    assert ip in action.error_message
    mock_build_client.assert_not_called()


@patch("polyswarm_modules.action_polyswarm_scanip.build_client")
def test_refuses_a_value_that_is_not_an_ip(mock_build_client: MagicMock, action: ScanIp) -> None:
    response = action.run({"ip": "not-an-ip"})

    assert response is None
    assert action.error_message is not None
    assert "not a valid IP address" in action.error_message
    mock_build_client.assert_not_called()


@patch("polyswarm_modules.action_polyswarm_scanip.build_client")
def test_lookup_failure_returns_none_without_quoting_the_client(mock_build_client: MagicMock, action: ScanIp) -> None:
    """A lookup failure must not surface the client's own message, which carries the key."""
    mock_api = mock_build_client.return_value
    secret_message = "test-api-key was rejected by https://api.polyswarm.network/v3"
    mock_api.search_url.side_effect = ps_exceptions.UsageLimitsExceededException(secret_message)

    response = action.run({"ip": "8.8.8.8"})

    assert response is None
    assert action.error_message is not None
    assert secret_message not in action.error_message
    mock_api.submit.assert_not_called()


@patch("polyswarm_modules.action_polyswarm_scanip.build_client")
def test_submit_failure_returns_none_without_quoting_the_client(mock_build_client: MagicMock, action: ScanIp) -> None:
    mock_api = mock_build_client.return_value
    mock_api.search_url.return_value = []
    secret_message = "test-api-key was rejected by https://api.polyswarm.network/v3"
    mock_api.submit.side_effect = ps_exceptions.PolyswarmAPIException(secret_message)

    response = action.run({"ip": "8.8.8.8"})

    assert response is None
    assert action.error_message is not None
    assert secret_message not in action.error_message
