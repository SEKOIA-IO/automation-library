from easyvista_modules.action_base import EasyVistaAction
from easyvista_modules.helpers import map_fields
from easyvista_modules.models import UpdateRequestIncidentArguments


class UpdateRequestIncident(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = UpdateRequestIncidentArguments(**arguments)
        body = map_fields(
            args,
            {
                "description": "Description",
                "urgency_id": "Urgency_ID",
                "external_reference": "External_reference",
                "asset": "ASSET",
                "asset_serial": "ASSET_SERIAL",
                "ci": "CI",
                "ci_id": "CI_ID",
            },
        )
        if not body:
            self.error("Nothing to update: provide at least one field")
            return None
        if not self.ensure_open(args.rfc_number):
            return None
        params = {"append": str(args.append).lower()} if args.append is not None else {}
        return self.request_href("PUT", self.request_path(args.rfc_number), json=body, params=params)
