import requests
from sekoia_automation.action import Action

from harfanglab.models import JobAction, JobTarget, JobTriggerResult


class JobExecutor(Action):
    def trigger_job(self, target: JobTarget, actions: list[JobAction]) -> JobTriggerResult:
        instance_url: str = self.module.configuration["url"]
        api_token: str = self.module.configuration["api_token"]

        job_url = f"{instance_url}/api/data/Job/"
        params: dict = {
            "targets": target.dict(),
            "actions": [action.dict() for action in actions],
        }

        response = requests.post(url=job_url, json=params, headers={"Authorization": f"Token {api_token}"})
        response.raise_for_status()
        return JobTriggerResult(**response.json()[0])
