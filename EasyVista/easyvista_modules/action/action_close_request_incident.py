from easyvista_modules.action_base import EasyVistaAction
from easyvista_modules.helpers import map_fields
from easyvista_modules.models import CloseRequestIncidentArguments


class CloseRequestIncident(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = CloseRequestIncidentArguments(**arguments)
        if not self.ensure_open(args.rfc_number):
            return None
        body = map_fields(
            args,
            {
                "status_guid": "STATUS_GUID",
                "comment": "COMMENT",
                "end_date": "END_DATE",
                "catalog_guid": "CATALOG_GUID",
                "delete_actions": "DELETE_ACTIONS",
            },
        )
        if args.delete_actions is not None:
            body["DELETE_ACTIONS"] = int(args.delete_actions)
        return self.request_href("PUT", self.request_path(args.rfc_number, "close"), json=body)
