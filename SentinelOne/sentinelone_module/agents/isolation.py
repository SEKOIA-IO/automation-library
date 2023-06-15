from management.mgmtsdk_v2.services.agent_actions import AgentsDangerousActionFilter
from pydantic import BaseModel

from sentinelone_module.base import SentinelOneAction
from sentinelone_module.filters import BaseFilters


class IsolateEndpointArguments(BaseFilters):
    account_ids: list[str] | None
    group_ids: list[str] | None
    ids: list[str] | None
    site_ids: list[str] | None
    query: str | None

    class Config:
        query_filter_class = AgentsDangerousActionFilter


class IsolateEndpointResults(BaseModel):
    affected: int


class IsolateEndpointAction(SentinelOneAction):
    name = "Isolate Endpoint"
    description = "Disconnect the endpoint from the network"
    results_model = IsolateEndpointResults

    def run(self, arguments: IsolateEndpointArguments):
        result = self.client.agent_actions.disconnect_from_network(query_filter=arguments.to_query_filter())
        return result.json["data"]


class DeisolateEndpointAction(SentinelOneAction):
    name = "Deisolate Endpoint"
    description = "Connect the endpoint back to the network"
    results_model = IsolateEndpointResults

    def run(self, arguments: IsolateEndpointArguments):
        result = self.client.agent_actions.connect_to_network(query_filter=arguments.to_query_filter())
        return result.json["data"]
