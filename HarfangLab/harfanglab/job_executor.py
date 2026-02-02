import time
import uuid
from abc import ABC
from functools import cached_property
from typing import Any
from urllib.parse import urljoin

import orjson
import requests
from sekoia_automation.action import Action

from .client import ApiClient
from .models import JobAction, JobBatchInformation, JobTarget, JobTriggerResult


class JobExecutor(Action, ABC):
    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(instance_url=self.module.configuration["url"], token=self.module.configuration["api_token"])

    @property
    def job_endpoint(self) -> str:
        # After deprecation of the old endpoint, we use the new one.
        return f"{self.client.instance_url}/api/data/job/batch/"

    def trigger_job(self, target: JobTarget, job: JobAction) -> JobTriggerResult:
        params: dict[str, Any] = {
            "targets": target.dict(exclude_none=True),
            "jobs": [job.as_params()],
        }

        response: requests.Response = self.client.post(url=self.job_endpoint, json=params)
        response.raise_for_status()

        job_result = JobTriggerResult(**response.json(), action=job.value, parameters=job.params)
        return job_result

    def wait_for_job_completion(self, job_id: str, timeout: int = 600) -> None:  # pragma: no cover
        """Wait until all job actions are done. Caution, can wait forever."""

        job_info: JobBatchInformation | None = None
        job_is_running = True

        time_start = time.time()

        while job_is_running:
            response: requests.Response = self.client.get(url=f"{self.job_endpoint}{job_id}/")
            response.raise_for_status()

            job_info = JobBatchInformation(**response.json())
            job_is_running = job_info.status.is_running()

            time_spent = time.time() - time_start
            if time_spent > timeout:
                raise TimeoutError(
                    f"JobExecutor.wait_for_job_completion() exceeded timeout of {timeout}s",
                )

            if job_is_running:
                time.sleep(1)

        if job_info is None:
            raise RuntimeError(f"No job information returned for job id {job_id}")

        if job_info.status.error > 0:
            self.log(
                message=f"One or more tasks failed for job id {job_id}",  # pragma: no cover
                level="error",
            )

        if job_info.status.canceled > 0:
            self.log(
                message=f"One or more tasks have been canceled for job id {job_id}",  # pragma: no cover
                level="warning",
            )

    def get_paginated_results(self, endpoint: str) -> list[dict]:
        results = []
        url = urljoin(self.client.instance_url, endpoint)

        while True:
            response: requests.Response = self.client.get(url=url)
            response.raise_for_status()

            js = response.json()

            results.extend(js.get("results", []))
            next_url = js.get("next")

            if next_url:
                url = urljoin(self.client.instance_url, next_url)

            else:
                break

        return results

    def save_to_file(self, js: list[dict] | dict) -> str:
        file_path = self.data_path / str(uuid.uuid4())
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "wb") as file:
            file.write(orjson.dumps(js))

        result_path = file_path.relative_to(self.data_path)
        return str(result_path)
