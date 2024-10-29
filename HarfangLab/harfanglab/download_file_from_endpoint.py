# coding: utf-8
import hashlib
import io
import pathlib
import shutil
import tempfile
import urllib.parse
import uuid
from typing import Any, TypeAlias

import requests
import tenacity
from tenacity import retry_if_exception_message, stop_after_delay, wait_exponential

from harfanglab.job_executor import JobExecutor
from harfanglab.models import JobAction, JobTarget

StrOrUUID4: TypeAlias = str | uuid.UUID


class DownloadFileFromEndpointAction(JobExecutor):
    """
    Action to download a single file from an HarfangLab endpoint
    """

    _artefact_info: dict[str, Any] | None = None
    _artefact_info_fetched: bool = False

    @property
    def artefact_sha256(self) -> str:
        if not self._artefact_info_fetched:
            raise RuntimeError("DownloadFileFromEndpointAction.fetch_artefact_info() not called")
        if self._artefact_info is None:
            # Note: This raise is mostly for semantic/mypy purpose and should never
            # happen in real life (an error will always raise before).
            raise RuntimeError(
                "DownloadFileFromEndpointAction.fetch_artefact_info() has been called, "
                "but '_artifact_info' is still None - Something really strange and wrong happen"
            )
        return self._artefact_info["sha256"]

    @tenacity.retry(
        stop=stop_after_delay(30),  # Aggregation can take some time.
        wait=wait_exponential(min=0.5, max=5),
        retry=retry_if_exception_message(match="No artefact info available for job"),
        reraise=True,
    )
    def fetch_artefact_info(self, job_id: StrOrUUID4, agent_id: StrOrUUID4) -> None:

        artefact_info_endpoint: str = urllib.parse.urljoin(
            base=self.instance_url,
            url="/api/data/investigation/artefact/Artefact/",
        )

        params: dict[str, Any] = {
            "job_id": str(job_id),
            "agent_id": str(agent_id),
        }

        response: requests.Response = requests.get(artefact_info_endpoint, params=params, headers=self.auth_headers)
        response.raise_for_status()

        results_count: int = response.json()["count"]

        if results_count == 0:
            raise ValueError(f"No artefact info available for job {job_id}")

        if results_count > 1:
            raise ValueError(f"Expected 1 result maximum, got {results_count} for job {job_id}")

        # At this point, results_count is granted to be 1,
        # and response.json()["results"] to have one and only one element.
        artefact_info = response.json()["results"][0]

        if artefact_info["job_id"] != job_id:
            raise ValueError(
                f"Given job id and the one in the fetched artefact info missmatch "
                f"(expected '{job_id}', got '{artefact_info['job_id']}')"
            )

        if artefact_info["agent"]["agentid"] != agent_id:
            raise ValueError(
                f"Given agent id and the one in the fetched artefact info missmatch "
                f"(expected '{agent_id}', got '{artefact_info['agent']['agentid']}')"
            )

        # Status 0 mean a successful download on endpoint, anything else other is an error.
        if artefact_info["download_status"] != 0:
            raise ValueError(
                f"Something went wrong while downloading the file on endpoint - "
                f"Does the targeted file exist on endpoint {agent_id}?"
            )

        self._artefact_info = artefact_info
        self._artefact_info_fetched = True

    def fetch_artefact_data(self, verify_digest: bool = False) -> io.IOBase:

        artefact_download_endpoint: str = urllib.parse.urljoin(
            base=self.instance_url,
            url=f"/api/data/telemetry/Binary/download/{self.artefact_sha256}/",
        )

        response: requests.Response = requests.get(artefact_download_endpoint, headers=self.auth_headers, stream=True)
        response.raise_for_status()

        buffer = tempfile.SpooledTemporaryFile(max_size=50_000_000)  # 50MiB max. into memory
        chunk: bytes

        for chunk in response.iter_content(chunk_size=None):
            buffer.write(chunk)

        buffer.seek(0)

        if verify_digest:

            hasher = hashlib.sha256()

            while chunk := buffer.read(io.DEFAULT_BUFFER_SIZE):
                hasher.update(chunk)

            if hasher.hexdigest() != self.artefact_sha256:
                raise ValueError(
                    f"Computed sha256 digest and the one in the fetched artefact info missmatch "
                    f"(expected '{self.artefact_sha256}', got '{hasher.hexdigest()}')"
                )

            buffer.seek(0)

        return buffer

    def run(self, arguments: dict[str, Any]) -> dict[str, str]:

        agent_id: str = arguments["id"]
        path_to_download: str = arguments["path"]

        job_target = JobTarget(agents=[agent_id], groups=[])
        job_action = JobAction(
            label="Downloadfile",
            value="downloadFile",
            params={
                "filename": path_to_download,
            },
        )

        self.trigger_job(target=job_target, actions=[job_action])
        self.wait_for_job_completion()

        self.fetch_artefact_info(self.job_id, agent_id)

        binary_data: io.IOBase = self.fetch_artefact_data(verify_digest=True)

        output_fp: pathlib.Path = self._data_path / self.artefact_sha256
        output_fp.parent.mkdir(parents=True, exist_ok=True)

        with binary_data as fd1, output_fp.open("wb") as fd2:
            shutil.copyfileobj(fd1, fd2)

        return {"path": str(output_fp)}
