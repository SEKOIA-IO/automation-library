import time

import requests
from sekoia_automation.action import Action

from harfanglab.models import JobAction, JobStatus, JobTarget, JobTriggerResult


class JobExecutor(Action):

    _job_id: str | None = None
    _job_is_running: bool | None = None

    @property
    def instance_url(self) -> str:
        return self.module.configuration["url"]

    @property
    def api_token(self) -> str:
        return self.module.configuration["api_token"]

    @property
    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Token {self.api_token}"}

    @property
    def job_endpoint(self) -> str:
        return f"{self.instance_url.rstrip('/')}/api/data/Job/"

    @property
    def job_id(self) -> str:
        if self._job_id is None:
            raise RuntimeError("JobExecutor.trigger_job() not called")  # pragma: no cover
        return self._job_id

    def job_is_running(self) -> bool:
        if self._job_is_running is None:
            raise RuntimeError("JobExecutor.trigger_job() not called")  # pragma: no cover
        return self._job_is_running

    def trigger_job(self, target: JobTarget, actions: list[JobAction]) -> JobTriggerResult:

        params: dict = {
            "targets": target.dict(),
            "actions": [action.dict() for action in actions],
        }

        response: requests.Response = requests.post(url=self.job_endpoint, json=params, headers=self.auth_headers)
        response.raise_for_status()

        job_result = JobTriggerResult(**response.json()[0])

        self._job_id = job_result.id
        self._job_is_running = True

        return job_result

    def wait_for_job_completion(self) -> None:  # pragma: no cover
        """Wait until all job actions are done. Caution, can wait forever."""

        job_status: JobStatus | None = None

        while self.job_is_running():

            response: requests.Response = requests.get(
                url=f"{self.job_endpoint}{self.job_id}/", headers=self.auth_headers
            )
            response.raise_for_status()

            job_status = JobStatus(**response.json())
            self._job_is_running = job_status.is_running()

            if self.job_is_running():
                time.sleep(1)

        if job_status is None:
            raise RuntimeError("JobExecutor.wait_for_job_completion() can only be called once")  # pragma: no cover

        if job_status.error > 0:
            self.log(
                message=f"One or more tasks failed for job id {self.job_id}",  # pragma: no cover
                level="error",
            )

        if job_status.canceled > 0:
            self.log(
                message=f"One or more tasks have been canceled for job id {self.job_id}",  # pragma: no cover
                level="warning",
            )
