from easyvista_modules.action_base import EasyVistaAction
from easyvista_modules.helpers import map_fields
from easyvista_modules.models import SuspendRequestIncidentArguments


class SuspendRequestIncident(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = SuspendRequestIncidentArguments(**arguments)
        body = map_fields(args, {"comment": "comment", "done_by_id": "done_by_id"})
        return self.request_href("PUT", self.request_path(args.rfc_number, "suspend"), json=body)
