# coding: utf-8
from time import sleep

from .job_executor import JobExecutor
from .models import JobAction, JobTarget, JobTriggerResult


class GetPipeListAction(JobExecutor):
    """
    Action to analyze an HarfangLab job that lists the named pipes
    """

    def get_pipes_by_job_id(self, job_id: str) -> list[dict]:
        return self.get_paginated_results(endpoint=f"/api/data/investigation/hunting/Pipe/?job_id={job_id}&limit=50")

    def run(self, arguments) -> dict:
        target_agents = arguments.get("target_agents", "")
        target_groups = arguments.get("target_groups", "")
        save_to_file = arguments.get("save_to_file", False)

        job_trigger_result: JobTriggerResult = self.trigger_job(
            target=JobTarget(
                agent_ids=[agent.strip() for agent in target_agents.split(",") if agent.strip()] or None,
                group_ids=[group.strip() for group in target_groups.split(",") if group.strip()] or None,
            ),
            job=JobAction(value="getPipeList", params={}),
        )
        self.wait_for_job_completion(job_id=job_trigger_result.id)

        # For some reason, even if a job marked as Done, we could get 0 results if we request them right away
        sleep(5)

        results = self.get_pipes_by_job_id(job_id=job_trigger_result.id)
        if save_to_file:
            path = self.save_to_file(results)
            return {"file_path": path}

        return {"results": results}
