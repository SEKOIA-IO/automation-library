from typing import ClassVar
from management.common.query_filter import QueryFilter
from management.mgmtsdk_v2_1.services.agent_actions import AgentActionsFilter
from pydantic import BaseModel

from sentinelone_module.base import SentinelOneAction
from sentinelone_module.filters import BaseFilters


class InitiateScanArguments(BaseFilters):
    account_ids: list[str] | None = None
    group_ids: list[str] | None = None
    uuids: list[str] | None = None
    site_ids: list[str] | None = None

    query_filter_class: ClassVar[type[QueryFilter]] = AgentActionsFilter


class InitiateScanResults(BaseModel):
    affected: int


class InitiateScanAction(SentinelOneAction):
    name = "Initiate Scan"
    description = "Run a Full Disk Scan on Agents that match the filter"
    results_model = InitiateScanResults

    def run(self, arguments: InitiateScanArguments):
        result = self.client.agent_actions.initiate_scan(query_filter=arguments.to_query_filter())
        return result.json["data"]
