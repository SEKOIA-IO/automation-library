from easyvista_modules.action_base import EasyVistaAction
from easyvista_modules.helpers import select_fields
from easyvista_modules.models import ViewRequestIncidentArguments


class ViewRequestIncident(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = ViewRequestIncidentArguments(**arguments)
        data = self.get(self.request_path(args.rfc_number))
        if data is None:
            return None
        return {**(select_fields(data, {"href": "HREF"}) or {}), "record": data}
