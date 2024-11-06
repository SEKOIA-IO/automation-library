import contextlib
import os
import pathlib
import re
import unittest.mock
from collections.abc import Iterator
from typing import Any, Optional, Type, TypeAlias

import pytest
import requests_mock

from harfanglab.download_file_from_endpoint import DownloadFileFromEndpointAction
from harfanglab.job_executor import JobExecutor

JSONResponse: TypeAlias = dict[str, Any]

_fake_instance_url: str = "http://non-existant.local"
_fake_api_token: str = "<--the-fake-api-token-->"
_fake_agent_id: str = "<--the-fake-agent-id-->"
_fake_job_id: str = "<--the-fake-job-id-->"
_fake_sha256_digest: str = "<--the-fake-sha256-digest-->"
_fake_artefact_content: bytes = b"\x13\x37"


class _fake_response:

    # Only the strict necessary for tests are present.
    artefact_info: JSONResponse = {
        "count": 1,
        "results": [
            {
                "agent": {
                    "agentid": _fake_agent_id,
                },
                "job_id": _fake_job_id,
                "download_status": 0,
                "sha256": _fake_sha256_digest,
            }
        ],
    }

    artefact_info_no_result: JSONResponse = {
        "count": 0,
    }

    artefact_info_too_many_results: JSONResponse = {
        "count": 1337,
    }

    artefact_info_missmatch_job_id: JSONResponse = {
        "count": 1,
        "results": [
            {
                "agent": {
                    "agentid": _fake_agent_id,
                },
                "job_id": _fake_job_id + "-missmatch-suffix",
            }
        ],
    }

    artefact_info_missmatch_agent_id: JSONResponse = {
        "count": 1,
        "results": [
            {
                "agent": {
                    "agentid": _fake_agent_id + "-missmatch-suffix",
                },
                "job_id": _fake_job_id,
            }
        ],
    }

    artefact_info_download_fail_on_endpoint: JSONResponse = {
        "count": 1,
        "results": [
            {
                "agent": {
                    "agentid": _fake_agent_id,
                },
                "job_id": _fake_job_id,
                "download_status": 1,
            }
        ],
    }


def _run_action(
    *,
    output_directory: Optional[pathlib.Path] = None,
    url: Optional[str] = None,
    api_token: Optional[str] = None,
    agent_id: Optional[str] = None,
    tenacity_enabled: bool = False,
) -> dict[str, Any]:
    """Simple wrapper to easily run the action."""

    tenacity_original_max_delay: int = DownloadFileFromEndpointAction.fetch_artefact_info.retry.stop.max_delay  # type: ignore[attr-defined]

    if not tenacity_enabled:
        # Disable the tenacity retrying mechanism.
        DownloadFileFromEndpointAction.fetch_artefact_info.retry.stop.max_delay = 0  # type: ignore[attr-defined]

    action = DownloadFileFromEndpointAction(data_path=output_directory)
    action.module.configuration = {
        "url": url or _fake_instance_url,
        "api_token": api_token or _fake_api_token,
    }

    arguments = {
        "id": agent_id or _fake_agent_id,
        "path": "C:\\WINDOWS\\SYSTEM32\\ntdll.dll",  # Granted to exist on a Windows endpoint.
    }

    try:
        return action.run(arguments)
    finally:
        # Re-enable tenacity.
        DownloadFileFromEndpointAction.fetch_artefact_info.retry.stop.max_delay = tenacity_original_max_delay  # type: ignore[attr-defined]


@contextlib.contextmanager
def job_executor_mock() -> Iterator[None]:
    """Mock for JobExecutor."""

    def trigger_job_side_effect(*_, **__) -> None:
        JobExecutor._job_id = _fake_job_id
        JobExecutor._job_is_running = True

    def wait_for_job_completion_side_effect(*_, **__) -> None:
        JobExecutor._job_is_running = False

    with (
        unittest.mock.patch.object(JobExecutor, "trigger_job") as mock1,
        unittest.mock.patch.object(JobExecutor, "wait_for_job_completion") as mock2,
    ):
        mock1.side_effect = trigger_job_side_effect
        mock2.side_effect = wait_for_job_completion_side_effect
        yield None
        mock1.assert_called_once()
        mock2.assert_called_once()

    JobExecutor._job_id = None
    JobExecutor._job_is_running = None


@contextlib.contextmanager
def hashlib_sha256_mock() -> Iterator[None]:
    """Mock for hashlib.sha256."""
    with unittest.mock.patch("hashlib.sha256") as mock:
        mock.return_value.hexdigest.return_value = _fake_sha256_digest
        yield None


def test_download_file_from_endpoint_success(symphony_storage) -> None:
    """Test scenario - Successful execution."""
    with (
        requests_mock.Mocker() as requests_mocker,
        job_executor_mock(),
        hashlib_sha256_mock(),
    ):
        requests_mocker.get(
            f"{_fake_instance_url}/api/data/investigation/artefact/Artefact/?job_id={_fake_job_id}&agent_id={_fake_agent_id}",
            status_code=200,
            json=_fake_response.artefact_info,
        )

        requests_mocker.get(
            f"{_fake_instance_url}/api/data/telemetry/Binary/download/{_fake_sha256_digest}/",
            status_code=200,
            content=_fake_artefact_content,
        )

        result = _run_action(output_directory=symphony_storage)

        assert result["path"] == str(symphony_storage / _fake_sha256_digest)

        with open(result["path"], "rb") as fd:
            assert fd.read() == _fake_artefact_content


@pytest.mark.parametrize(
    "fake_response, error_type, error_msg_pattern",
    [
        (
            _fake_response.artefact_info_no_result,
            ValueError,
            f"No artefact info available for job {_fake_job_id}",
        ),
        (
            _fake_response.artefact_info_too_many_results,
            ValueError,
            "Expected 1 result maximum",
        ),
        (
            _fake_response.artefact_info_missmatch_job_id,
            ValueError,
            "Given job id and the one in the fetched artefact info missmatch",
        ),
        (
            _fake_response.artefact_info_missmatch_agent_id,
            ValueError,
            "Given agent id and the one in the fetched artefact info missmatch",
        ),
        (
            _fake_response.artefact_info_download_fail_on_endpoint,
            ValueError,
            "Something went wrong while downloading the file on endpoint",
        ),
    ],
)
def test_fetch_artefact_info_fail(
    fake_response: JSONResponse,
    error_type: Type[BaseException],
    error_msg_pattern: str,
) -> None:
    """Test scenario - Misc fail scenario on artefact info fetching."""

    with (
        requests_mock.Mocker() as requests_mocker,
        job_executor_mock(),
    ):
        requests_mocker.get(
            f"{_fake_instance_url}/api/data/investigation/artefact/Artefact/?job_id={_fake_job_id}&agent_id={_fake_agent_id}",
            status_code=200,
            json=fake_response,
        )

        with pytest.raises(error_type, match=error_msg_pattern):
            _run_action()


def test_fetch_artefact_data_runtime_error_fetch_artefact_info_not_called() -> None:
    """Test runtime error when fetching the artefact data and info wasn't fetched first.
    Should never happen in real life, that mostly a developer watchdog."""
    with (
        job_executor_mock(),
        # Mock the fetch_artefact_info method to simulate the "it was never called".
        unittest.mock.patch.object(
            target=DownloadFileFromEndpointAction,
            attribute="fetch_artefact_info",
        ),
        pytest.raises(
            expected_exception=RuntimeError,
            match=".+?" + re.escape(".fetch_artefact_info() not called"),
        ),
    ):
        _run_action()


def test_fetch_artefact_data_runtime_error_fetch_artefact_info_called() -> None:
    """Test runtime error when fetching the artefact data and info wasn't fetched first.
    Should never happen in real life, that mostly a semantic issue."""

    def fetch_artefact_info_side_effect(*_, **__) -> None:
        DownloadFileFromEndpointAction._artefact_info = None
        DownloadFileFromEndpointAction._artefact_info_fetched = True

    with (
        job_executor_mock(),
        unittest.mock.patch.object(
            target=DownloadFileFromEndpointAction,
            attribute="fetch_artefact_info",
            side_effect=fetch_artefact_info_side_effect,
        ),
        pytest.raises(
            expected_exception=RuntimeError,
            match=".+?" + re.escape(".fetch_artefact_info() has been called"),
        ),
    ):
        _run_action()

    DownloadFileFromEndpointAction._artefact_info = None
    DownloadFileFromEndpointAction._artefact_info_fetched = False


def test_fetch_artefact_data_digest_missmatch() -> None:
    """Test scenario - Digest from downloaded file and the one from EDR missmatch."""
    with (
        requests_mock.Mocker() as requests_mocker,
        job_executor_mock(),
    ):
        requests_mocker.get(
            f"{_fake_instance_url}/api/data/investigation/artefact/Artefact/?job_id={_fake_job_id}&agent_id={_fake_agent_id}",
            status_code=200,
            json=_fake_response.artefact_info,
        )

        requests_mocker.get(
            f"{_fake_instance_url}/api/data/telemetry/Binary/download/{_fake_sha256_digest}/",
            status_code=200,
            content=_fake_artefact_content,
        )

        with pytest.raises(
            ValueError, match="Computed sha256 digest and the one in the fetched artefact info missmatch"
        ):
            _run_action()


@pytest.mark.skipif(
    """not all(map(os.environ.get, ("HARFANGLAB_URL", "HARFANGLAB_API_TOKEN", "HARFANGLAB_AGENT_ID")))""",
)
def test_integration_download_file_from_endpoint(symphony_storage) -> None:
    """Live test - Run only if some envvars are present."""
    result = _run_action(
        output_directory=symphony_storage,
        url=os.environ["HARFANGLAB_URL"],
        api_token=os.environ["HARFANGLAB_API_TOKEN"],
        agent_id=os.environ["HARFANGLAB_AGENT_ID"],
        tenacity_enabled=True,
    )

    with open(result["path"], "rb") as fd:
        assert fd.read(8) == b"MZ\x90\x00\x03\x00\x00\x00"
