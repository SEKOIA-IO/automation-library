from typing import ClassVar

from harfanglab.base import HarfanglabAction

base_url = "/api/data"


class EndpointAgentIsolationAction(HarfanglabAction):
    verb = "post"
    endpoint = base_url + "/endpoint/Agent/{id}/isolate/"
    query_parameters: ClassVar[list[str]] = []


class EndpointAgentDeisolationAction(HarfanglabAction):
    verb = "post"
    endpoint = base_url + "/endpoint/Agent/{id}/deisolate/"
    query_parameters: ClassVar[list[str]] = []


class EndpointGroupIsolationAction(HarfanglabAction):
    verb = "post"
    endpoint = base_url + "/endpoint/Group/{id}/isolation/"
    query_parameters: ClassVar[list[str]] = []


class EndpointGroupDeisolationAction(HarfanglabAction):
    verb = "post"
    endpoint = base_url + "/endpoint/Group/{id}/deisolation/"
    query_parameters: ClassVar[list[str]] = []
