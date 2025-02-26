from stormshield_module.base import StormshieldAction

base_url = "/agents/{id}/tasks"


class TerminateProcessAction(StormshieldAction):
    verb = "post"
    endpoint = base_url + "/process-termination"
    query_parameters: list[str] = []
