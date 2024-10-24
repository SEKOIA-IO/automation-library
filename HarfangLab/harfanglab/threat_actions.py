from harfanglab.base import HarfanglabAction

base_url = "/api/data"


class AddCommentToThreat(HarfanglabAction):
    verb = "post"
    endpoint = base_url + "/alert/alert/Threat/{id}/comment/"
    query_parameters: list[str] = []


class UpdateThreatStatus(HarfanglabAction):
    verb = "patch"
    endpoint = base_url + "/alert/alert/Threat/status/"
    query_parameters: list[str] = []
