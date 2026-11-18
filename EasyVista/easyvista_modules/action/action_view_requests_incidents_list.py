from easyvista_modules.action_base import EasyVistaAction
from easyvista_modules.helpers import LIST_FIELDS, select_fields
from easyvista_modules.models import ViewRequestsIncidentsListArguments


class ViewRequestsIncidentsList(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = ViewRequestsIncidentsListArguments(**arguments)
        return select_fields(self.get("/requests", params=args.model_dump(exclude_none=True)), LIST_FIELDS)
