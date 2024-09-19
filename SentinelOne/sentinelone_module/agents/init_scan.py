from management.mgmtsdk_v2_1.services.agent_actions import AgentActionsFilter
from pydantic import BaseModel

from sentinelone_module.base import SentinelOneAction
from sentinelone_module.filters import BaseFilters


class InitiateScanArguments(BaseFilters):
    account_ids: list[str] | None
    group_ids: list[str] | None
    uuids: list[str] | None
    site_ids: list[str] | None

    class Config:
        query_filter_class = AgentActionsFilter


class InitiateScanResults(BaseModel):
    affected: int


class InitiateScanAction(SentinelOneAction):
    name = "Initiate Scan"
    description = "Run a Full Disk Scan on Agents that match the filter"
    results_model = InitiateScanResults

    def run(self, arguments: InitiateScanArguments):
        result = self.client.agent_actions.initiate_scan(query_filter=arguments.to_query_filter())
        return result.json["data"]
