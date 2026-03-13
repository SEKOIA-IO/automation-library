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

from .job_executor import JobExecutor
from .models import JobAction, JobTarget

StrOrUUID4: TypeAlias = str | uuid.UUID


class DownloadFileFromEndpointAction(JobExecutor):
    """
    Action to download a single file from an HarfangLab endpoint
    """

    @tenacity.retry(
        stop=stop_after_delay(30),  # Aggregation can take some time.
        wait=wait_exponential(min=0.5, max=5),
        retry=retry_if_exception_message(match="No artefact info available for job"),
        reraise=True,
    )
    def fetch_artefact_info(self, job_id: StrOrUUID4, agent_id: StrOrUUID4) -> dict[str, Any]:
        artefact_info_endpoint: str = urllib.parse.urljoin(
            base=self.client.instance_url,
            url="/api/data/investigation/artefact/Artefact/",
        )

        params: dict[str, Any] = {
            "job_id": str(job_id),
            "agent_id": str(agent_id),
        }

        response: requests.Response = self.client.get(artefact_info_endpoint, params=params)
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

        return artefact_info

    def fetch_artefact_data(self, artefact_info: dict[str, Any], verify_digest: bool = False) -> io.IOBase:
        artefact_sha256 = artefact_info.get("sha256")
        if not artefact_sha256 or not isinstance(artefact_sha256, str):
            raise RuntimeError("Missing or invalid 'sha256' in artefact_info when fetching artefact data")

        artefact_download_endpoint: str = urllib.parse.urljoin(
            base=self.client.instance_url,
            url=f"/api/data/telemetry/Binary/download/{artefact_sha256}/",
        )

        response: requests.Response = self.client.get(artefact_download_endpoint, stream=True)
        response.raise_for_status()

        buffer = tempfile.SpooledTemporaryFile(max_size=50_000_000)  # 50MB max. into memory
        chunk: bytes

        for chunk in response.iter_content(chunk_size=None):
            buffer.write(chunk)

        buffer.seek(0)

        if verify_digest:

            hasher = hashlib.sha256()

            while chunk := buffer.read(io.DEFAULT_BUFFER_SIZE):
                hasher.update(chunk)

            if hasher.hexdigest() != artefact_sha256:
                raise ValueError(
                    f"Computed sha256 digest and the one in the fetched artefact info missmatch "
                    f"(expected '{artefact_sha256}', got '{hasher.hexdigest()}')"
                )

            buffer.seek(0)

        return buffer

    def run(self, arguments: dict[str, Any]) -> dict[str, str]:

        agent_id: str = arguments["id"]
        path_to_download: str = arguments["path"]

        job_target = JobTarget(agent_ids=[agent_id])
        job_action = JobAction(
            value="downloadFile",
            params=[
                {
                    "filename": path_to_download,
                }
            ],
        )

        job_trigger_result = self.trigger_job(target=job_target, job=job_action)
        self.wait_for_job_completion(job_id=job_trigger_result.id)

        artifact_info = self.fetch_artefact_info(job_id=job_trigger_result.id, agent_id=agent_id)

        binary_data: io.IOBase = self.fetch_artefact_data(artefact_info=artifact_info, verify_digest=True)

        output_fp: pathlib.Path = self._data_path / artifact_info["sha256"]
        output_fp.parent.mkdir(parents=True, exist_ok=True)

        with binary_data as fd1, output_fp.open("wb") as fd2:
            shutil.copyfileobj(fd1, fd2)

        return {"path": str(output_fp)}
