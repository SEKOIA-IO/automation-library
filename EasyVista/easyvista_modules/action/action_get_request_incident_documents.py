from easyvista_modules.action_base import EasyVistaAction
from easyvista_modules.helpers import select_fields
from easyvista_modules.models import GetRequestIncidentDocumentsArguments


class GetRequestIncidentDocuments(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = GetRequestIncidentDocumentsArguments(**arguments)
        return select_fields(
            self.get(self.request_path(args.rfc_number, "documents")),
            {"href": "HREF", "parent_href": "PARENT_HREF", "documents": "Documents"},
        )
