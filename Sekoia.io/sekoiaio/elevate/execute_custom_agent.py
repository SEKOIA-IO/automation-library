from time import sleep, time
from typing import Any

from pydantic import BaseModel

from sekoiaio.elevate.agent import BaseAgent


class AgentExecutionError(Exception):
    """Raised when an Agent run ends in an error or cannot be monitored."""


class ExecuteCustomAgentArguments(BaseModel):
    agent_uuid: str


class ExecuteCustomAgentResults(BaseModel):
    status: str
    uuid: str
    community_uuid: str
    agent_uuid: str
    run_name: str | None
    started_at: str
    ended_at: str
    duration_seconds: float
    credits: str
    output: Any = None


class AgentRunBody(BaseModel):
    key: str
    instructions: str
    tools: list
    skill_uuids: list
    response_format: dict


class RunBody(BaseModel):
    community_uuid: str
    agent: AgentRunBody
    initial_state: dict
    scope_type: str
    scope_uuid: str


class ExecuteCustomAgent(BaseAgent):
    results_model = ExecuteCustomAgentResults

    def build_agent_body(self, agent: dict) -> RunBody:
        playbook_uuid = self.module.playbook_uuid
        playbook_run_uuid = self.module.playbook_run_uuid
        node_run_uuid = self.module.node_run_uuid

        agent_body = AgentRunBody(
            key=f"{playbook_uuid}:{playbook_run_uuid}+{node_run_uuid}",
            instructions=agent["instructions"],
            tools=agent["tools"],
            skill_uuids=agent["skill_uuids"],
            response_format=agent["response_format"],
        )

        return RunBody(
            community_uuid=agent["community_uuid"],
            agent=agent_body,
            initial_state={},
            scope_type="playbook_run",
            scope_uuid=playbook_run_uuid,
        )

    def trigger_error(self, message: str, run_uuid: str, error: Any = None) -> None:
        self.log(
            message,
            level="error",
            run_uuid=run_uuid,
            error=error,
        )
        raise AgentExecutionError(message)

    def catch_error(self, run: dict) -> None:
        match run["status"]:
            case "error":
                error = run.get("error")
                self.trigger_error(f"Agent run '{run['uuid']}' ended with error: {error}", run["uuid"], error)
            case "out_of_quota":
                self.trigger_error(f"Agent run '{run['uuid']}' ended with quota limit", run["uuid"])
            case "rate_limited":
                self.trigger_error(f"Agent run '{run['uuid']}' reached a rate limit", run["uuid"])
            case "cancelled":
                self.trigger_error(f"Agent run '{run['uuid']}' was cancelled", run["uuid"])

    def wait_agent_run_status(self, agent_run_uuid: str, timeout: int) -> dict:
        run = self.get_agent_run(agent_run_uuid)
        self.catch_error(run)

        start_wait = time()

        while run["status"] in ("pending", "in_progress"):
            sleep(1)

            run = self.get_agent_run(agent_run_uuid)
            self.catch_error(run)

            if time() - start_wait > timeout:
                raise TimeoutError(f"Timeout while waiting for agent run '{agent_run_uuid}' to complete.")

        if run["status"] != "completed":
            self.trigger_error(f"Agent run '{run['uuid']}' ended with unexpected status: {run['status']}", run["uuid"])

        return run

    def run(self, arguments: ExecuteCustomAgentArguments) -> ExecuteCustomAgentResults:
        self.configure_url()
        self.configure_http_session()

        agent = self.get_agent(arguments.agent_uuid)
        agent_body = self.build_agent_body(agent)

        agent_run_uuid = self.execute_agent(agent_body)
        run = self.wait_agent_run_status(agent_run_uuid, timeout=1200)

        return ExecuteCustomAgentResults(**run)
