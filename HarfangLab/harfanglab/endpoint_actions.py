# coding: utf-8

from harfanglab.base import HarfanglabAction

base_url = "/api/data"


class EndpointAgentIsolationAction(HarfanglabAction):
    verb = "post"
    endpoint = base_url + "/endpoint/Agent/{id}/isolate/"
    query_parameters: list[str] = []


class EndpointAgentDeisolationAction(HarfanglabAction):
    verb = "post"
    endpoint = base_url + "/endpoint/Agent/{id}/deisolate/"
    query_parameters: list[str] = []


class EndpointGroupIsolationAction(HarfanglabAction):
    verb = "post"
    endpoint = base_url + "/endpoint/Group/{id}/isolation/"
    query_parameters: list[str] = []


class EndpointGroupDeisolationAction(HarfanglabAction):
    verb = "post"
    endpoint = base_url + "/endpoint/Group/{id}/deisolation/"
    query_parameters: list[str] = []
