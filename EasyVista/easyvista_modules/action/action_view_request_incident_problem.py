from easyvista_modules.action_base import EasyVistaAction
from easyvista_modules.helpers import LIST_FIELDS, select_fields
from easyvista_modules.models import ViewRequestIncidentProblemArguments


class ViewRequestIncidentProblem(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = ViewRequestIncidentProblemArguments(**arguments)
        return select_fields(self.get(self.request_path(args.rfc_number, "problem")), LIST_FIELDS)
