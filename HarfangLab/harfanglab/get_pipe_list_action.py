# coding: utf-8

# natives

# third parties
from harfanglab.job_executor import JobExecutor
from harfanglab.models import JobAction, JobTarget, JobTriggerResult


class GetPipeListAction(JobExecutor):
    """
    Action to analyze an HarfangLab job that lists the named pipes
    """

    def run(self, arguments) -> dict:
        target_agents = arguments.get("target_agents", "")
        target_groups = arguments.get("target_groups", "")

        job_trigger_result: JobTriggerResult = self.trigger_job(
            target=JobTarget(
                agents=[agent.strip() for agent in target_agents.split(",") if agent.strip()],
                groups=[group.strip() for group in target_groups.split(",") if group.strip()],
            ),
            actions=[JobAction(label="Pipelist", value="getPipeList")],
        )

        return job_trigger_result.dict()
