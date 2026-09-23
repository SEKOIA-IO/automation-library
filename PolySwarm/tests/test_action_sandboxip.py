from unittest.mock import MagicMock, patch

import pytest
from polyswarm_api import exceptions as ps_exceptions
from requests import RequestException

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_sandboxip import SandboxIp


@pytest.fixture
def action(data_storage: str, module: PolyswarmModule) -> SandboxIp:
    return SandboxIp(module=module, data_path=data_storage)


def _make_provider(slug: str, artifact_types: tuple[str, ...] = ("FILE", "URL")) -> MagicMock:
    """A provider shaped like the real one: the image list is where a vm slug comes from."""
    provider = MagicMock()
    provider.slug = slug
    provider.json = {
        "slug": slug,
        "vms": {
            f"{slug}-image": {
                "slug": f"{slug}-image",
                "supported_artifact_types": list(artifact_types),
            }
        },
    }
    return provider


def _make_artifact_instance(sha256: str = "aa" * 32) -> MagicMock:
    instance = MagicMock()
    instance.sha256 = sha256
    return instance


def _make_sandbox_task(
    *,
    task_id: str = "task-123",
    sha256: str = "aa" * 32,
    sandbox: str = "cape",
    status: str = "PENDING",
    report: dict | None = None,
    community: str = "default",
) -> MagicMock:
    task = MagicMock()
    task.id = task_id
    task.sha256 = sha256
    task.sandbox = sandbox
    task.status = status
    task.report = report
    task.community = community
    return task


# --- Submission and the honest target field ------------------------------


@patch("polyswarm_modules.action_polyswarm_sandboxip.build_client")
def test_submits_the_converted_url_and_reports_the_detonated_target(
    mock_build_client: MagicMock, action: SandboxIp
) -> None:
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.search_url.side_effect = ps_exceptions.NoResultsException("no results")
    mock_api.sandbox_url.return_value = _make_sandbox_task(status="PENDING")

    response = action.run({"ip": "8.8.8.8"})
    assert response is not None

    mock_api.sandbox_url.assert_called_once_with(
        "http://8.8.8.8/",
        provider_slug="cape",
        vm_slug="cape-image",
    )
    # The result must carry the exact target that was actually detonated,
    # so an analyst reading it understands why it shows a URL.
    assert response["target"] == "http://8.8.8.8/"
    assert response["ip"] == "8.8.8.8"
    assert response["already_analysed"] is False
    assert action._outputs == {"submitted": True}


@patch("polyswarm_modules.action_polyswarm_sandboxip.build_client")
def test_ipv6_target_is_bracketed(mock_build_client: MagicMock, action: SandboxIp) -> None:
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.search_url.side_effect = ps_exceptions.NoResultsException("no results")
    mock_api.sandbox_url.return_value = _make_sandbox_task(status="PENDING")

    response = action.run({"ip": "2001:4860:4860::8888"})
    assert response is not None

    assert response["target"] == "http://[2001:4860:4860::8888]/"


@patch("polyswarm_modules.action_polyswarm_sandboxip.build_client")
def test_does_not_block_by_default(mock_build_client: MagicMock, action: SandboxIp) -> None:
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.search_url.side_effect = ps_exceptions.NoResultsException("no results")
    mock_api.sandbox_url.return_value = _make_sandbox_task(status="PENDING")

    action.run({"ip": "8.8.8.8"})

    mock_api.sandbox_task_status.assert_not_called()


# --- Already analysed branch --------------------------------------------


@patch("polyswarm_modules.action_polyswarm_sandboxip.build_client")
def test_already_analysed_when_existing_report_found(mock_build_client: MagicMock, action: SandboxIp) -> None:
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.search_url.return_value = [_make_artifact_instance()]
    existing = _make_sandbox_task(status="SUCCEEDED", report={"ok": True})
    mock_api.sandbox_task_latest.return_value = existing

    response = action.run({"ip": "8.8.8.8"})
    assert response is not None

    mock_api.search_url.assert_called_once_with("http://8.8.8.8/")
    mock_api.sandbox_task_latest.assert_called_once_with("aa" * 32, sandbox="cape")
    mock_api.sandbox_url.assert_not_called()
    assert response["already_analysed"] is True
    assert response["target"] == "http://8.8.8.8/"
    assert action._outputs == {"already analysed": True}


@patch("polyswarm_modules.action_polyswarm_sandboxip.build_client")
def test_force_skips_lookup(mock_build_client: MagicMock, action: SandboxIp) -> None:
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.sandbox_url.return_value = _make_sandbox_task(status="PENDING")

    response = action.run({"ip": "8.8.8.8", "force": True})
    assert response is not None

    mock_api.search_url.assert_not_called()
    mock_api.sandbox_url.assert_called_once()
    assert response["already_analysed"] is False


# --- Refusals, using ScanIp's wording ------------------------------------


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
@patch("polyswarm_modules.action_polyswarm_sandboxip.build_client")
def test_refuses_non_public_addresses(mock_build_client: MagicMock, action: SandboxIp, ip: str) -> None:
    response = action.run({"ip": ip})

    assert response is None
    assert action.error_message is not None
    assert ip in action.error_message
    mock_build_client.assert_not_called()


@patch("polyswarm_modules.action_polyswarm_sandboxip.build_client")
def test_refuses_a_value_that_is_not_an_ip(mock_build_client: MagicMock, action: SandboxIp) -> None:
    response = action.run({"ip": "not-an-ip"})

    assert response is None
    assert action.error_message is not None
    assert "not a valid IP address" in action.error_message
    mock_build_client.assert_not_called()


# --- Provider validation --------------------------------------------------


@patch("polyswarm_modules.action_polyswarm_sandboxip.build_client")
def test_refuses_unknown_provider(mock_build_client: MagicMock, action: SandboxIp) -> None:
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape"), _make_provider("triage")]

    response = action.run({"ip": "8.8.8.8", "sandbox": "not-a-provider"})

    assert response is None
    assert action.error_message is not None
    assert "not-a-provider" in action.error_message
    mock_api.sandbox_url.assert_not_called()


@patch("polyswarm_modules.action_polyswarm_sandboxip.build_client")
def test_an_image_named_by_the_author_is_used_without_asking_the_platform(
    mock_build_client: MagicMock, action: SandboxIp
) -> None:
    """Naming an image is the escape hatch when the provider list cannot be read."""
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.side_effect = RequestException("connection reset")
    mock_api.search_url.side_effect = ps_exceptions.NoResultsException("no results")
    mock_api.sandbox_task_latest.side_effect = ps_exceptions.NoResultsException("no results")
    mock_api.sandbox_url.return_value = _make_sandbox_task(status="PENDING")
    mock_api.sandbox_file.return_value = _make_sandbox_task(status="PENDING")

    response = action.run({**{"ip": "8.8.8.8"}, "vm_slug": "chosen-by-hand"})

    assert response is not None
    assert response["vm_slug"] == "chosen-by-hand"


@patch("polyswarm_modules.action_polyswarm_sandboxip.build_client")
def test_no_image_and_no_provider_list_refuses_rather_than_guessing(
    mock_build_client: MagicMock, action: SandboxIp
) -> None:
    """Guessing an image is how this module shipped one that did not exist."""
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.side_effect = RequestException("connection reset")
    mock_api.search_url.side_effect = ps_exceptions.NoResultsException("no results")
    mock_api.sandbox_task_latest.side_effect = ps_exceptions.NoResultsException("no results")

    response = action.run({"ip": "8.8.8.8"})

    assert response is None
    assert "sandbox image" in action.error_message
    mock_api.sandbox_url.assert_not_called()
    mock_api.sandbox_file.assert_not_called()


# --- Failures never quote the client -----------------------------------


@patch("polyswarm_modules.action_polyswarm_sandboxip.build_client")
def test_submit_failure_returns_none_without_quoting_the_client(
    mock_build_client: MagicMock, action: SandboxIp
) -> None:
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.search_url.side_effect = ps_exceptions.NoResultsException("no results")
    secret_message = "test-api-key was rejected by https://api.polyswarm.network/v3"
    mock_api.sandbox_url.side_effect = ps_exceptions.PolyswarmAPIException(secret_message)

    response = action.run({"ip": "8.8.8.8"})

    assert response is None
    assert action.error_message is not None
    assert secret_message not in action.error_message


# --- Optional wait --------------------------------------------------------


@patch("polyswarm_modules.action_polyswarm_sandboxip.time")
@patch("polyswarm_modules.action_polyswarm_sandboxip.build_client")
def test_wait_reaches_a_verdict(mock_build_client: MagicMock, mock_time: MagicMock, action: SandboxIp) -> None:
    mock_time.monotonic.return_value = 0.0
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.search_url.side_effect = ps_exceptions.NoResultsException("no results")
    mock_api.sandbox_url.return_value = _make_sandbox_task(status="RUNNING")
    mock_api.sandbox_task_status.return_value = _make_sandbox_task(status="SUCCEEDED", report={"ok": True})

    response = action.run({"ip": "8.8.8.8", "wait": True})

    assert response is not None
    assert response["status"] == "SUCCEEDED"
    mock_api.sandbox_task_status.assert_called_once()


@patch("polyswarm_modules.action_polyswarm_sandboxip.time")
@patch("polyswarm_modules.action_polyswarm_sandboxip.build_client")
def test_wait_hits_its_ceiling_still_processing(
    mock_build_client: MagicMock, mock_time: MagicMock, action: SandboxIp
) -> None:
    mock_time.monotonic.side_effect = [0.0, 5.0]
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.search_url.side_effect = ps_exceptions.NoResultsException("no results")
    mock_api.sandbox_url.return_value = _make_sandbox_task(status="RUNNING")

    response = action.run({"ip": "8.8.8.8", "wait": True, "max_wait_seconds": 1})

    assert response is not None
    assert response["status"] == "RUNNING"
    mock_api.sandbox_task_status.assert_not_called()
    mock_time.sleep.assert_not_called()


def test_max_wait_seconds_is_capped_at_the_hard_ceiling() -> None:
    from pydantic import ValidationError

    from polyswarm_modules.action_polyswarm_sandboxip import SandboxIpArguments

    with pytest.raises(ValidationError):
        SandboxIpArguments(ip="8.8.8.8", wait=True, max_wait_seconds=900)


# --- Client construction ---------------------------------------------------


@patch("polyswarm_modules.action_polyswarm_sandboxip.build_client")
def test_uses_the_shared_retrying_client(
    mock_build_client: MagicMock, action: SandboxIp, module: PolyswarmModule
) -> None:
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.search_url.side_effect = ps_exceptions.NoResultsException("no results")
    mock_api.sandbox_url.return_value = _make_sandbox_task(status="PENDING")

    action.run({"ip": "8.8.8.8"})

    mock_build_client.assert_called_once_with(module.configuration)
