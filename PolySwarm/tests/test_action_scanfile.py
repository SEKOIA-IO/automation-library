from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from polyswarm_api import exceptions as ps_exceptions

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_scanfile import ScanFile


@pytest.fixture
def action(data_storage: str, module: PolyswarmModule) -> ScanFile:
    return ScanFile(module=module, data_path=data_storage)


@pytest.fixture
def sample_file(data_storage: str) -> str:
    """A file where Sekoia puts it, named the way a playbook refers to it."""
    path = Path(data_storage) / "malware.exe"
    path.write_bytes(b"sample bytes")
    return path.name


def _make_assertion(*, engine_name: str, author_name: str, verdict: bool | None, mask: bool = True) -> MagicMock:
    assertion = MagicMock()
    assertion.engine_name = engine_name
    assertion.author_name = author_name
    assertion.verdict = verdict
    assertion.mask = mask
    return assertion


def _make_scan_result(
    *,
    sha256: str = "abc123" * 10 + "ab",
    sha1: str = "def456" * 6 + "def4",
    md5: str = "aabb" * 8,
    extended_type: str = "PE32 executable (GUI) Intel 80386",
    polyscore: float = 0.95,
    permalink: str = "https://polyswarm.network/scan/results/test123",
    failed: bool = False,
    window_closed: bool = True,
    assertions: list[MagicMock] | None = None,
) -> MagicMock:
    if assertions is None:
        assertions = [
            _make_assertion(engine_name="ClamAV", author_name="clamav", verdict=True),
            _make_assertion(engine_name="Lionic", author_name="lionic", verdict=True),
            _make_assertion(engine_name="CleanEngine", author_name="clean", verdict=False),
        ]

    result = MagicMock()
    result.sha256 = sha256
    result.sha1 = sha1
    result.md5 = md5
    result.extended_type = extended_type
    result.polyscore = polyscore
    result.permalink = permalink
    result.failed = failed
    result.window_closed = window_closed
    result.assertions = assertions
    result.malicious_assertions = [a for a in assertions if a.mask and a.verdict]
    result.benign_assertions = [a for a in assertions if a.mask and not a.verdict]
    result.valid_assertions = [a for a in assertions if a.mask]
    return result


@patch("polyswarm_modules.action_polyswarm_scanfile._sha256_file", return_value="aa" * 32)
@patch("polyswarm_modules.action_polyswarm_scanfile.build_client")
def test_returns_cached_when_existing(
    mock_build_client: MagicMock, mock_hash: MagicMock, action: ScanFile, sample_file: str
) -> None:
    existing = _make_scan_result()
    mock_build_client.return_value.search.return_value = [existing]

    response = action.run({"file": sample_file})

    mock_build_client.return_value.search.assert_called_once_with("aa" * 32)
    mock_build_client.return_value.submit.assert_not_called()
    assert response["cached"] is True
    assert response["sha256"] == "abc123" * 10 + "ab"


@patch("polyswarm_modules.action_polyswarm_scanfile._sha256_file", return_value="aa" * 32)
@patch("polyswarm_modules.action_polyswarm_scanfile.build_client")
def test_submits_when_no_existing(
    mock_build_client: MagicMock, mock_hash: MagicMock, action: ScanFile, sample_file: str
) -> None:
    mock_api = mock_build_client.return_value
    mock_api.search.return_value = []
    mock_instance = MagicMock()
    mock_api.submit.return_value = mock_instance
    mock_api.wait_for.return_value = _make_scan_result()

    response = action.run({"file": sample_file})

    submitted = mock_api.submit.call_args.args[0]
    assert submitted.endswith("/malware.exe")
    assert mock_api.submit.call_args.kwargs == {"scan_config": "default"}
    mock_api.wait_for.assert_called_once_with(mock_instance)
    assert response["cached"] is False
    assert response["malicious_count"] == 2
    assert response["benign_count"] == 1


@patch("polyswarm_modules.action_polyswarm_scanfile._sha256_file", return_value="aa" * 32)
@patch("polyswarm_modules.action_polyswarm_scanfile.build_client")
def test_force_rescan_skips_lookup(
    mock_build_client: MagicMock, mock_hash: MagicMock, action: ScanFile, sample_file: str
) -> None:
    mock_api = mock_build_client.return_value
    mock_api.submit.return_value = MagicMock()
    mock_api.wait_for.return_value = _make_scan_result()

    response = action.run({"file": sample_file, "force_rescan": True})

    mock_api.search.assert_not_called()
    mock_api.submit.assert_called_once()
    assert response["cached"] is False


@patch("polyswarm_modules.action_polyswarm_scanfile._sha256_file", return_value="aa" * 32)
@patch("polyswarm_modules.action_polyswarm_scanfile.build_client")
def test_submits_when_existing_failed(
    mock_build_client: MagicMock, mock_hash: MagicMock, action: ScanFile, sample_file: str
) -> None:
    failed = _make_scan_result(failed=True)
    mock_api = mock_build_client.return_value
    mock_api.search.return_value = [failed]
    mock_api.submit.return_value = MagicMock()
    mock_api.wait_for.return_value = _make_scan_result()

    response = action.run({"file": sample_file})

    mock_api.submit.assert_called_once()
    assert response["cached"] is False


@patch("polyswarm_modules.action_polyswarm_scanfile._sha256_file", return_value="aa" * 32)
@patch("polyswarm_modules.action_polyswarm_scanfile.build_client")
def test_excludes_unmasked_assertions(
    mock_build_client: MagicMock, mock_hash: MagicMock, action: ScanFile, sample_file: str
) -> None:
    assertions = [
        _make_assertion(engine_name="ClamAV", author_name="clamav", verdict=True, mask=True),
        _make_assertion(engine_name="Ghost", author_name="ghost", verdict=False, mask=False),
    ]
    mock_build_client.return_value.search.return_value = []
    mock_build_client.return_value.submit.return_value = MagicMock()
    mock_build_client.return_value.wait_for.return_value = _make_scan_result(assertions=assertions)

    response = action.run({"file": sample_file})

    assert len(response["assertions"]) == 1
    assert response["assertions"][0]["engine_name"] == "ClamAV"


@patch("polyswarm_modules.action_polyswarm_scanfile.build_client")
def test_detections_activate_the_detected_branch(
    mock_build_client: MagicMock, action: ScanFile, sample_file: str
) -> None:
    """The branch is what a playbook author wires on the canvas, so it follows the counts."""
    mock_api = mock_build_client.return_value
    mock_api.search.return_value = []
    mock_api.submit.return_value = MagicMock()
    mock_api.wait_for.return_value = _make_scan_result()

    action.run({"file": sample_file})

    assert action._outputs == {"detected": True}


@patch("polyswarm_modules.action_polyswarm_scanfile.build_client")
def test_the_threshold_moves_the_branch(mock_build_client: MagicMock, action: ScanFile, sample_file: str) -> None:
    """A lone engine calling it malicious is the operator's judgement, not ours."""
    mock_api = mock_build_client.return_value
    mock_api.search.return_value = []
    mock_api.submit.return_value = MagicMock()
    mock_api.wait_for.return_value = _make_scan_result()

    action.run({"file": sample_file, "detect_threshold": 99})

    assert action._outputs == {"not detected": True}


@patch("polyswarm_modules.action_polyswarm_scanfile._sha256_file", return_value="aa" * 32)
@patch("polyswarm_modules.action_polyswarm_scanfile.build_client")
def test_uses_the_shared_retrying_client(
    mock_build_client: MagicMock, mock_hash: MagicMock, action: ScanFile, sample_file: str, module: PolyswarmModule
) -> None:
    """The action must build its client through build_client, not a bare PolyswarmAPI(), to get retries."""
    mock_api = mock_build_client.return_value
    mock_api.search.return_value = []
    mock_api.submit.return_value = MagicMock()
    mock_api.wait_for.return_value = _make_scan_result()

    action.run({"file": sample_file})

    mock_build_client.assert_called_once_with(module.configuration)


@patch("polyswarm_modules.action_polyswarm_scanfile._sha256_file", return_value="aa" * 32)
@patch("polyswarm_modules.action_polyswarm_scanfile.build_client")
def test_submit_failure_returns_none_without_quoting_the_client(
    mock_build_client: MagicMock, mock_hash: MagicMock, action: ScanFile, sample_file: str
) -> None:
    """A failure during submission must not surface the client's own message, which carries the key."""
    mock_api = mock_build_client.return_value
    mock_api.search.return_value = []
    secret_message = "test-api-key was rejected by https://api.polyswarm.network/v3"
    mock_api.submit.side_effect = ps_exceptions.PolyswarmAPIException(secret_message)

    response = action.run({"file": sample_file})

    assert response is None
    assert action.error_message is not None
    assert secret_message not in action.error_message


@patch("polyswarm_modules.action_polyswarm_scanfile._sha256_file", return_value="aa" * 32)
@patch("polyswarm_modules.action_polyswarm_scanfile.build_client")
def test_lookup_failure_returns_none_without_quoting_the_client(
    mock_build_client: MagicMock, mock_hash: MagicMock, action: ScanFile, sample_file: str
) -> None:
    mock_api = mock_build_client.return_value
    secret_message = "test-api-key was rejected by https://api.polyswarm.network/v3"
    mock_api.search.side_effect = ps_exceptions.UsageLimitsExceededException(secret_message)

    response = action.run({"file": sample_file})

    assert response is None
    assert action.error_message is not None
    assert secret_message not in action.error_message
    mock_api.submit.assert_not_called()
