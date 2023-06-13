# coding: utf-8

# natives

# third parties
from harfanglab.job_executor import JobExecutor
from harfanglab.models import JobAction, JobTarget, JobTriggerResult


class GetProcessListAction(JobExecutor):
    """
    Action to analyze an HarfangLab job that lists the process
    """

    def run(self, arguments) -> dict:
        target_agents = arguments.get("target_agents", "")
        target_groups = arguments.get("target_groups", "")
        get_connections_list = arguments.get("get_connections_list", False)
        get_handles_list = arguments.get("get_handles_list", False)
        get_signatures_list = arguments.get("get_signatures_list", False)

        job_trigger_result: JobTriggerResult = self.trigger_job(
            target=JobTarget(
                agents=[agent.strip() for agent in target_agents.split(",") if agent.strip()],
                groups=[group.strip() for group in target_groups.split(",") if group.strip()],
            ),
            actions=[
                JobAction(
                    label="Processes",
                    value="getProcessList",
                    params={
                        "getHandlesList": get_handles_list,
                        "getConnectionsList": get_connections_list,
                        "getSignaturesInfo": get_signatures_list,
                    },
                )
            ],
        )

        return job_trigger_result.dict()
