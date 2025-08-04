from stormshield_module.base import StormshieldAction

base_url = "/agents/{id}/tasks"


class QuarantineFileAction(StormshieldAction):
    verb = "post"
    endpoint = base_url + "/file-quarantine"
    query_parameters: list[str] = []


class RestoreQuarantinedFileAction(StormshieldAction):
    verb = "post"
    endpoint = base_url + "/quarantined-file-restoration"
    query_parameters: list[str] = []
