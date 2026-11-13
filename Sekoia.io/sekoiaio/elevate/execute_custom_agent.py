from time import sleep, time
from typing import Any
from uuid import UUID, uuid5

from pydantic import BaseModel

from sekoiaio.elevate.agent import BaseAgent


class AgentExecutionError(Exception):
    """Raised when an Agent run ends in an error or cannot be monitored."""


class ExecuteCustomAgentArguments(BaseModel):
    agent_uuid: str
    initial_state: dict | str | None = None


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


class RunBody(BaseModel):
    agent_uuid: str
    community_uuid: str
    initial_state: dict | str
    scope_type: str
    scope_uuid: str


class ExecuteCustomAgent(BaseAgent):
    results_model = ExecuteCustomAgentResults

    def build_run_body(self, agent: dict, initial_state: dict | str | None = None) -> RunBody:
        # The run is for the community of the playbook: it may differ from the one owning the agent,
        # e.g. for an agent a parent community shares with its subcommunities
        community_uuid = self.module.community_uuid or agent["community_uuid"]

        return RunBody(
            # Run the catalog agent by its UUID: copying its definition inline would require
            # fields the agent may leave unset, such as its instructions
            agent_uuid=agent["uuid"],
            community_uuid=community_uuid,
            # A string is the content of a single user message; without one, the agent's instructions
            # describe its whole task
            initial_state=initial_state or {},
            # The run is always scoped: outside a playbook run (e.g. a manual test of the action),
            # it falls back to a UUID derived from the community, as the API requires a UUID
            # but does not check that the playbook run exists
            scope_type="playbook_run",
            scope_uuid=self.module.playbook_run_uuid or str(uuid5(UUID(community_uuid), "playbook-run")),
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
        run_body = self.build_run_body(agent, arguments.initial_state)

        agent_run_uuid = self.execute_agent(run_body)
        run = self.wait_agent_run_status(agent_run_uuid, timeout=1200)

        return ExecuteCustomAgentResults(**run)
