import requests
from sekoia_automation.action import Action
import time
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
    def job_instance_id(self) -> str:
        if self._job_id is None:
            raise RuntimeError("JobExecutor.trigger_job() not called")
        return self._job_id

    @property
    def job_instance_endpoint(self) -> str:
        return f"{self.job_endpoint}{self.job_instance_id}/"

    def job_is_running(self) -> bool:
        if self._job_is_running is None:
            raise RuntimeError("JobExecutor.trigger_job() not called")
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

    def wait_for_job_completion(self) -> None:
        """Wait until all job actions are done. Caution, can wait forever."""

        while self.job_is_running():

            response: requests.Response = requests.get(url=self.job_instance_endpoint, headers=self.auth_headers)
            response.raise_for_status()

            self._job_is_running = JobStatus(**response.json()).is_running()

            if self.job_is_running():
                time.sleep(1)
