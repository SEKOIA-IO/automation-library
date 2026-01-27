# coding: utf-8
from time import sleep

from .job_executor import JobExecutor
from .models import JobAction, JobTarget, JobTriggerResult


class GetProcessListAction(JobExecutor):
    """
    Action to analyze an HarfangLab job that lists the process
    """

    def get_processes_by_job_id(self, job_id: str) -> list[dict]:
        return self.get_paginated_results(
            endpoint=f"/api/data/investigation/hunting/Process/?job_id={job_id}&limit=50"
        )

    def run(self, arguments) -> dict:
        target_agents = arguments.get("target_agents", "")
        target_groups = arguments.get("target_groups", "")
        get_connections_list = arguments.get("get_connections_list", False)
        get_handles_list = arguments.get("get_handles_list", False)
        get_signatures_list = arguments.get("get_signatures_list", False)
        save_to_file = arguments.get("save_to_file", False)

        job_trigger_result: JobTriggerResult = self.trigger_job(
            target=JobTarget(
                agent_ids=[agent.strip() for agent in target_agents.split(",") if agent.strip()] or None,
                group_ids=[group.strip() for group in target_groups.split(",") if group.strip()] or None,
            ),
            job=JobAction(
                value="getProcessList",
                params={
                    "getHandlesList": get_handles_list,
                    "getConnectionsList": get_connections_list,
                    "getSignaturesInfo": get_signatures_list,
                },
            ),
        )
        self.wait_for_job_completion(job_id=job_trigger_result.id)

        # For some reason, even if a job marked as Done, we could get 0 results if we request them right away
        sleep(5)

        results = self.get_processes_by_job_id(job_id=job_trigger_result.id)

        if save_to_file:
            path = self.save_to_file(results)
            return {"file_path": path}

        return {"results": results}
