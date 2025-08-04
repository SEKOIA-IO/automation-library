from stormshield_module.base import StormshieldAction

base_url = "/agents/{id}/tasks"


class EndpointAgentIsolationAction(StormshieldAction):
    verb = "post"
    endpoint = base_url + "/network-isolation"
    query_parameters: list[str] = []


class EndpointAgentDeisolationAction(StormshieldAction):
    verb = "post"
    endpoint = base_url + "/network-deisolation"
    query_parameters: list[str] = []
