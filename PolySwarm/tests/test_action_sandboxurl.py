from unittest.mock import MagicMock, patch

import pytest
from polyswarm_api import exceptions as ps_exceptions
from requests import RequestException

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_sandboxurl import SandboxUrl


@pytest.fixture
def action(data_storage: str, module: PolyswarmModule) -> SandboxUrl:
    return SandboxUrl(module=module, data_path=data_storage)


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


# --- Submission --------------------------------------------------------


@patch("polyswarm_modules.action_polyswarm_sandboxurl.build_client")
def test_submits_when_no_existing_report(mock_build_client: MagicMock, action: SandboxUrl) -> None:
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.search_url.side_effect = ps_exceptions.NoResultsException("no results")
    mock_api.sandbox_url.return_value = _make_sandbox_task(status="PENDING")

    response = action.run({"url": "https://example.com/payload"})
    assert response is not None

    mock_api.sandbox_url.assert_called_once_with(
        "https://example.com/payload",
        provider_slug="cape",
        vm_slug="cape-image",
    )
    assert response["sandbox_task_id"] == "task-123"
    assert response["url"] == "https://example.com/payload"
    assert response["sha256"] == "aa" * 32
    assert response["already_analysed"] is False
    assert "task-123" in response["report_url"]
    assert action._outputs == {"submitted": True}


@patch("polyswarm_modules.action_polyswarm_sandboxurl.build_client")
def test_does_not_block_by_default(mock_build_client: MagicMock, action: SandboxUrl) -> None:
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.search_url.side_effect = ps_exceptions.NoResultsException("no results")
    mock_api.sandbox_url.return_value = _make_sandbox_task(status="PENDING")

    action.run({"url": "https://example.com/payload"})

    mock_api.sandbox_task_status.assert_not_called()


# --- Already analysed branch --------------------------------------------


@patch("polyswarm_modules.action_polyswarm_sandboxurl.build_client")
def test_already_analysed_when_existing_report_found(mock_build_client: MagicMock, action: SandboxUrl) -> None:
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.search_url.return_value = [_make_artifact_instance()]
    existing = _make_sandbox_task(status="SUCCEEDED", report={"ok": True})
    mock_api.sandbox_task_latest.return_value = existing

    response = action.run({"url": "https://example.com/payload"})
    assert response is not None

    mock_api.search_url.assert_called_once_with("https://example.com/payload")
    mock_api.sandbox_task_latest.assert_called_once_with("aa" * 32, sandbox="cape")
    mock_api.sandbox_url.assert_not_called()
    assert response["already_analysed"] is True
    assert action._outputs == {"already analysed": True}


@patch("polyswarm_modules.action_polyswarm_sandboxurl.build_client")
def test_no_existing_artifact_falls_through_to_submitting(mock_build_client: MagicMock, action: SandboxUrl) -> None:
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.search_url.return_value = []
    mock_api.sandbox_url.return_value = _make_sandbox_task(status="PENDING")

    response = action.run({"url": "https://example.com/payload"})
    assert response is not None

    mock_api.sandbox_task_latest.assert_not_called()
    mock_api.sandbox_url.assert_called_once()
    assert response["already_analysed"] is False


@patch("polyswarm_modules.action_polyswarm_sandboxurl.build_client")
def test_force_skips_lookup(mock_build_client: MagicMock, action: SandboxUrl) -> None:
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.sandbox_url.return_value = _make_sandbox_task(status="PENDING")

    response = action.run({"url": "https://example.com/payload", "force": True})
    assert response is not None

    mock_api.search_url.assert_not_called()
    mock_api.sandbox_url.assert_called_once()
    assert response["already_analysed"] is False


# --- Scheme refusal ---------------------------------------------------


@pytest.mark.parametrize("url", ["ftp://example.com/file", "example.com/no-scheme", "javascript:alert(1)"])
@patch("polyswarm_modules.action_polyswarm_sandboxurl.build_client")
def test_refuses_a_non_http_scheme(mock_build_client: MagicMock, action: SandboxUrl, url: str) -> None:
    response = action.run({"url": url})

    assert response is None
    assert action.error_message is not None
    assert url in action.error_message
    mock_build_client.assert_not_called()


# --- Provider validation --------------------------------------------------


@patch("polyswarm_modules.action_polyswarm_sandboxurl.build_client")
def test_refuses_unknown_provider(mock_build_client: MagicMock, action: SandboxUrl) -> None:
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape"), _make_provider("triage")]

    response = action.run({"url": "https://example.com/payload", "sandbox": "not-a-provider"})

    assert response is None
    assert action.error_message is not None
    assert "not-a-provider" in action.error_message
    mock_api.sandbox_url.assert_not_called()


@patch("polyswarm_modules.action_polyswarm_sandboxurl.build_client")
def test_an_image_named_by_the_author_is_used_without_asking_the_platform(
    mock_build_client: MagicMock, action: SandboxUrl
) -> None:
    """Naming an image is the escape hatch when the provider list cannot be read."""
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.side_effect = RequestException("connection reset")
    mock_api.search_url.side_effect = ps_exceptions.NoResultsException("no results")
    mock_api.sandbox_task_latest.side_effect = ps_exceptions.NoResultsException("no results")
    mock_api.sandbox_url.return_value = _make_sandbox_task(status="PENDING")
    mock_api.sandbox_file.return_value = _make_sandbox_task(status="PENDING")

    response = action.run({**{"url": "https://example.com/payload"}, "vm_slug": "chosen-by-hand"})

    assert response is not None
    assert response["vm_slug"] == "chosen-by-hand"


@patch("polyswarm_modules.action_polyswarm_sandboxurl.build_client")
def test_no_image_and_no_provider_list_refuses_rather_than_guessing(
    mock_build_client: MagicMock, action: SandboxUrl
) -> None:
    """Guessing an image is how this module shipped one that did not exist."""
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.side_effect = RequestException("connection reset")
    mock_api.search_url.side_effect = ps_exceptions.NoResultsException("no results")
    mock_api.sandbox_task_latest.side_effect = ps_exceptions.NoResultsException("no results")

    response = action.run({"url": "https://example.com/payload"})

    assert response is None
    assert "sandbox image" in action.error_message
    mock_api.sandbox_url.assert_not_called()
    mock_api.sandbox_file.assert_not_called()


# --- Failures never quote the client -----------------------------------


@patch("polyswarm_modules.action_polyswarm_sandboxurl.build_client")
def test_submit_failure_returns_none_without_quoting_the_client(
    mock_build_client: MagicMock, action: SandboxUrl
) -> None:
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.search_url.side_effect = ps_exceptions.NoResultsException("no results")
    secret_message = "test-api-key was rejected by https://api.polyswarm.network/v3"
    mock_api.sandbox_url.side_effect = ps_exceptions.PolyswarmAPIException(secret_message)

    response = action.run({"url": "https://example.com/payload"})

    assert response is None
    assert action.error_message is not None
    assert secret_message not in action.error_message


@patch("polyswarm_modules.action_polyswarm_sandboxurl.build_client")
def test_search_url_failure_falls_through_to_submitting(mock_build_client: MagicMock, action: SandboxUrl) -> None:
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    secret_message = "test-api-key was rejected by https://api.polyswarm.network/v3"
    mock_api.search_url.side_effect = ps_exceptions.PolyswarmAPIException(secret_message)
    mock_api.sandbox_url.return_value = _make_sandbox_task(status="PENDING")

    response = action.run({"url": "https://example.com/payload"})

    assert response is not None
    assert secret_message not in (action.error_message or "")
    mock_api.sandbox_url.assert_called_once()


# --- Optional wait --------------------------------------------------------


@patch("polyswarm_modules.action_polyswarm_sandboxurl.time")
@patch("polyswarm_modules.action_polyswarm_sandboxurl.build_client")
def test_wait_reaches_a_verdict(mock_build_client: MagicMock, mock_time: MagicMock, action: SandboxUrl) -> None:
    mock_time.monotonic.return_value = 0.0
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.search_url.side_effect = ps_exceptions.NoResultsException("no results")
    mock_api.sandbox_url.return_value = _make_sandbox_task(status="RUNNING")
    mock_api.sandbox_task_status.return_value = _make_sandbox_task(status="SUCCEEDED", report={"ok": True})

    response = action.run({"url": "https://example.com/payload", "wait": True})

    assert response is not None
    assert response["status"] == "SUCCEEDED"
    mock_api.sandbox_task_status.assert_called_once()


@patch("polyswarm_modules.action_polyswarm_sandboxurl.time")
@patch("polyswarm_modules.action_polyswarm_sandboxurl.build_client")
def test_wait_hits_its_ceiling_still_processing(
    mock_build_client: MagicMock, mock_time: MagicMock, action: SandboxUrl
) -> None:
    mock_time.monotonic.side_effect = [0.0, 5.0]
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.search_url.side_effect = ps_exceptions.NoResultsException("no results")
    mock_api.sandbox_url.return_value = _make_sandbox_task(status="RUNNING")

    response = action.run({"url": "https://example.com/payload", "wait": True, "max_wait_seconds": 1})

    assert response is not None
    assert response["status"] == "RUNNING"
    mock_api.sandbox_task_status.assert_not_called()
    mock_time.sleep.assert_not_called()


def test_max_wait_seconds_is_capped_at_the_hard_ceiling() -> None:
    from pydantic import ValidationError

    from polyswarm_modules.action_polyswarm_sandboxurl import SandboxUrlArguments

    with pytest.raises(ValidationError):
        SandboxUrlArguments(url="https://example.com", wait=True, max_wait_seconds=900)


# --- Client construction ---------------------------------------------------


@patch("polyswarm_modules.action_polyswarm_sandboxurl.build_client")
def test_uses_the_shared_retrying_client(
    mock_build_client: MagicMock, action: SandboxUrl, module: PolyswarmModule
) -> None:
    mock_api = mock_build_client.return_value
    mock_api.sandbox_providers.return_value = [_make_provider("cape")]
    mock_api.search_url.side_effect = ps_exceptions.NoResultsException("no results")
    mock_api.sandbox_url.return_value = _make_sandbox_task(status="PENDING")

    action.run({"url": "https://example.com/payload"})

    mock_build_client.assert_called_once_with(module.configuration)
